#!/usr/bin/env python3
"""Déjà View corpus: sample past launches, fingerprint them, fetch outcomes, backtest.

Rules are frozen in docs/CORPUS_PLAN.md. This file implements them.

    .venv/bin/python corpus.py collect    # Stages 1 and 2: sample events and fingerprint them
    .venv/bin/python corpus.py outcomes   # Stage 3: prices after the decision point
    .venv/bin/python corpus.py build      # write data/corpus.json, no credits
    .venv/bin/python corpus.py analyze    # backtest and verdict, no credits

State lives in spike_out/corpus/. Every stage resumes from its saved state.
"""

import datetime as dt
import json
import math
import random
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor

import d3
import launch_data as ld
import matching as mt
from nansen_client import OUT, NansenClient, utc
from reflex import HISTORY_DIR, MAX_BUYERS, Scanner

DIR = OUT / "corpus"
DIR.mkdir(exist_ok=True)
DATES = sorted(d3.DATES + d3.EXTRA_DATES)
ROUNDS = 3
MAX_CHECK = 30
MIN_BUYERS = 6
TARGET = 50
MIN_EVENTS = 30
CAP = 12_000
STAGE2_STOP = 11_400
EVENT_RESERVE = 400
RERUNS = 2
SEED = 20260914
SHUFFLES = 5000
LN10 = math.log(10)
HORIZONS = {"ret6h": dt.timedelta(hours=6), "ret24h": dt.timedelta(hours=24), "ret7d": dt.timedelta(days=7)}


def load(name, default):
    p = DIR / name
    return json.loads(p.read_text()) if p.exists() else default


def save(name, data):
    (DIR / name).write_text(json.dumps(data, indent=2, default=str))


class Budget:
    """Spend against the corpus start balance, from the credit header."""

    def __init__(self, c):
        self.c = c
        state = load("state.json", {})
        if "start_balance" not in state:
            state["start_balance"] = self.ledger_balance()
            state["started_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            save("state.json", state)
        self.start = state["start_balance"]
        self.last_left = None

    def ledger_balance(self):
        for line in reversed(self.c.ledger_path.read_text().splitlines()):
            v = json.loads(line).get("headers", {}).get("x-nansen-credits-remaining")
            if v is not None:
                return int(v)
        sys.exit("No credit balance in the call log. Make one request first.")

    def spent(self):
        left = self.c.last_headers.get("x-nansen-credits-remaining")
        if left is not None:
            self.last_left = int(left)
        if self.last_left is None:
            self.last_left = self.ledger_balance()
        return self.start - self.last_left

    def ok(self, limit, reserve=0):
        return self.spent() + reserve <= limit


def retry(fn, tries=3):
    for _ in range(tries):
        got = fn()
        if got is not None:
            return got
    return None


def seed_history():
    """Reuse D3 wallet histories. D3 fetched the same 30-day windows before the same T0."""
    wallets = d3.load("wallets.json", {})
    HISTORY_DIR.mkdir(exist_ok=True)
    for w, v in wallets.items():
        src, dst = d3.D3 / "history" / f"{w}.json", HISTORY_DIR / f"{w}.json"
        if src.exists() and not dst.exists():
            t0 = utc(v["t0"])
            dst.write_text(json.dumps({"from": (t0 - 30 * ld.DAY).isoformat(), "to": t0.isoformat(),
                                      "trades": json.loads(src.read_text())}))


# --------------------------------------------------------------------------- Stages 1 and 2

def next_event(c, scanner, date, rec):
    """Check candidates in hash order until one is eligible. Records every check."""
    cands = d3.candidates(d3.screener(c, date))
    day = dt.date.fromisoformat(date)
    now = dt.datetime.now(dt.timezone.utc)
    while len(rec["checked"]) < min(MAX_CHECK, len(cands)):
        t = cands[len(rec["checked"])]
        info = retry(lambda: ld.resolve_t0(c, t, scanner.t0_cache))
        scanner.t0_cache.save()
        row = {"token": t}
        if info is None:
            row["result"] = "skipped_api_failure"
        elif not info.get("deployment_timestamp") or not info.get("t0_timestamp"):
            row["result"] = "no_t0"
        elif utc(info["deployment_timestamp"]).date() != day:
            row["result"] = "not_deployed_on_date"
        elif utc(info["t0_timestamp"]) - utc(info["deployment_timestamp"]) > ld.LAUNCH_WINDOW:
            row["result"] = "t0_after_6h"
        else:
            deploy, t0 = utc(info["deployment_timestamp"]), utc(info["t0_timestamp"])
            try:
                buyers = scanner.first_hour_buys(t, deploy, t0, now)
            except RuntimeError:
                buyers = None
            if buyers is None:
                row["result"] = "skipped_api_failure"
            elif len(buyers) < MIN_BUYERS:
                row["result"] = "too_few_buyers"
                row["buyers"] = len(buyers)
            else:
                row.update(result="event", symbol=info.get("symbol"), deployment=deploy.isoformat(),
                           t0=t0.isoformat(), buyers=buyers)
        rec["checked"].append(row)
        if row["result"] == "event":
            return row
    return None


def score_event(scanner, date, ev):
    t0 = utc(ev["t0"])
    top = ev["buyers"][:MAX_BUYERS]
    for attempt in range(1 + RERUNS):
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda b: scanner.score_wallet(b, t0), top))
        scanner.t0_cache.save()
        scanner.market.save()
        failures = sum(r.get("api_failures", 0) for r in results)
        if not failures:
            break
    features, reason = mt.fingerprint(ev["buyers"], results)
    keep = ("usd", "buys", "entry_delay_s", "window_usd", "scoreable", "reflex", "prior_launch_entries",
            "runner_rate", "failed_launch_rate", "api_failures")
    return {"date": date, "token": ev["token"], "symbol": ev["symbol"], "deployment": ev["deployment"],
            "t0": ev["t0"], "buyers": len(ev["buyers"]), "scoreable": sum(r["scoreable"] for r in results),
            "api_failures": failures, "attempts": attempt + 1,
            "top": [{k: r.get(k) for k in keep} for r in results],
            "all_buyer_usd": [b["usd"] for b in ev["buyers"]],
            "features": features, "no_fingerprint_reason": reason,
            "scored_at": dt.datetime.now(dt.timezone.utc).isoformat()}


def collect(c, budget):
    state = load("state.json", {})
    if state.get("collection_done"):
        print("Collection already finished:", state["collection_done"])
        return
    seed_history()
    scanner = Scanner(c)
    dates = load("dates.json", {})
    scored = load("scored.json", {})

    def fingerprinted():
        return sum(1 for s in scored.values() if s["features"])

    def finish(reason):
        state = load("state.json", {})
        state["collection_done"] = {"reason": reason, "fingerprinted": fingerprinted(), "events": len(scored),
                                    "spent": budget.spent(),
                                    "events_per_date": {d: sum(1 for s in scored.values() if s["date"] == d)
                                                        for d in DATES}}
        save("state.json", state)
        print("Collection finished:", state["collection_done"])

    for rnd in range(1, ROUNDS + 1):
        for date in DATES:
            if fingerprinted() >= TARGET:
                return finish("target reached")
            rec = dates.setdefault(date, {"checked": []})
            found = [r for r in rec["checked"] if r["result"] == "event"]
            if len(found) < rnd:
                if len(rec["checked"]) >= MAX_CHECK:
                    continue
                if not budget.ok(STAGE2_STOP, EVENT_RESERVE):
                    save("dates.json", dates)
                    return finish("budget stop")
                ev = next_event(c, scanner, date, rec)
                save("dates.json", dates)
                if ev is None:
                    print(f"round {rnd} {date}: no further eligible candidate ({len(rec['checked'])} checked)")
                    continue
            else:
                ev = found[rnd - 1]
            if ev["token"] in scored:
                continue
            if not budget.ok(STAGE2_STOP, EVENT_RESERVE):
                return finish("budget stop")
            scored[ev["token"]] = score_event(scanner, date, ev)
            save("scored.json", scored)
            s = scored[ev["token"]]
            print(f"round {rnd} {date} {s['symbol']}: buyers={s['buyers']} scoreable={s['scoreable']} "
                  f"fingerprint={'yes' if s['features'] else 'no'} failures={s['api_failures']} "
                  f"fingerprinted={fingerprinted()} spent={budget.spent()}")
    finish("all rounds finished")


# --------------------------------------------------------------------------- Stage 3

def outcomes(c, budget):
    state = load("state.json", {})
    if not state.get("collection_done"):
        sys.exit("Stage 2 has not finished. Outcomes wait until collection stops.")
    scored = load("scored.json", {})
    got = load("outcomes.json", {})
    now = dt.datetime.now(dt.timezone.utc)
    jobs = [s for s in scored.values() if s["features"] and s["token"] not in got]

    def job(s):
        base_t = utc(s["t0"]) + dt.timedelta(hours=1)
        base = retry(lambda: ld.price_at(c, s["token"], base_t, f"corpus:out:{s['token'][:6]}:base", now))
        if base is None:
            return s["token"], None
        rec = {"base_time": base_t.isoformat(), "base": base}
        for name, h in HORIZONS.items():
            p = retry(lambda: ld.price_at(c, s["token"], base_t + h, f"corpus:out:{s['token'][:6]}:{name}", now))
            if p is None:
                return s["token"], None
            rec[name] = p
        rec["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        return s["token"], rec

    if not budget.ok(CAP, 8 * len(jobs)):
        sys.exit("STOP: outcomes would pass the budget cap.")
    with ThreadPoolExecutor(8) as pool:
        for token, rec in pool.map(job, jobs):
            if rec is not None:
                got[token] = rec
    save("outcomes.json", got)
    print(f"Outcomes stored for {len(got)} events; {len(jobs) - sum(1 for s in jobs if s['token'] in got)} "
          f"failed and can be rerun. Spent {budget.spent()}.")


# --------------------------------------------------------------------------- build and analyze

def capped(p, base):
    if not base:
        return None
    return -LN10 if not p else max(-LN10, min(LN10, math.log(p / base)))


def build():
    scored = load("scored.json", {})
    got = load("outcomes.json", {})
    state = load("state.json", {})
    events, no_base = [], 0
    for s in sorted(scored.values(), key=lambda s: (s["date"], s["t0"])):
        o = got.get(s["token"])
        if not s["features"] or not o:
            continue
        base = o["base"]["price"]
        if not base:
            no_base += 1
            continue
        out = {}
        for name in HORIZONS:
            p = o[name]["price"]
            out[name] = capped(p, base)
            out[name + "_pct"] = round(100 * (p / base - 1), 1)
            out[name + "_no_trades"] = not p
        events.append({"date": s["date"], "token": s["token"], "symbol": s["symbol"],
                       "deployment": s["deployment"], "t0": s["t0"], "buyers": s["buyers"],
                       "scoreable_buyers": s["scoreable"],
                       "features": {k: round(v, 4) for k, v in s["features"].items()},
                       "outcomes": out, "fetched_at": o["fetched_at"]})
    if len(events) < MIN_EVENTS:
        print(f"Only {len(events)} events with a fingerprint and outcomes; the minimum is {MIN_EVENTS}. Stopping.")
    stats = mt.scale(events) if len(events) > 1 else {}
    nearest = sorted(mt.neighbours(e["features"], events, stats, k=1, skip=lambda x, e=e: x is e)[0][0]
                     for e in events) if len(events) > 1 else []
    terciles = [nearest[len(nearest) // 3], nearest[2 * len(nearest) // 3]] if nearest else [0, 0]
    corpus = {"source": "docs/CORPUS_PLAN.md", "built_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "collection": state.get("collection_done"), "events_without_base_price": no_base,
              "scale": stats, "distance_terciles": terciles, "events": events,
              "backtest": (mt.load_corpus() or {}).get("backtest")}
    mt.CORPUS_FILE.write_text(json.dumps(corpus, indent=2))
    print(f"Wrote {mt.CORPUS_FILE} with {len(events)} events.")


def backtest(events, stats, outcome, only=mt.FEATURES):
    """Spearman correlation of each event's outcome with its 3 nearest other-date events' mean outcome."""
    lists = [[e2 for _, e2 in mt.neighbours(e["features"], events, stats,
                                            skip=lambda x, e=e: x["date"] == e["date"], only=only)]
             for e in events]
    idx = {id(e): i for i, e in enumerate(events)}
    nb = [[idx[id(x)] for x in lst] for lst in lists]
    y = [e["outcomes"][outcome] for e in events]

    def stat(vals):
        return d3.spearman(vals, [statistics.mean(vals[j] for j in js) for js in nb])

    real = stat(y)
    rng = random.Random(SEED)
    below, shuffled = 0, y[:]
    for _ in range(SHUFFLES):
        rng.shuffle(shuffled)
        below += stat(shuffled) < real
    return real, below / SHUFFLES


def analyze():
    corpus = mt.load_corpus()
    if not corpus or len(corpus["events"]) < MIN_EVENTS:
        sys.exit("Build a corpus with at least 30 events first.")
    events, stats = corpus["events"], corpus["scale"]
    rho, pct = backtest(events, stats, "ret24h")
    verdict = "SIGNAL" if rho > 0 and pct >= 0.95 else "NO SIGNAL SHOWN"
    print(f"Primary ret24h: rho={rho:.3f} percentile={pct:.1%} events={len(events)} -> {verdict}")
    reported = {}
    for o in ("ret6h", "ret7d"):
        r, p = backtest(events, stats, o)
        reported[o] = {"rho": round(r, 3), "percentile": round(p, 3)}
        print(f"Reported {o}: rho={r:.3f} percentile={p:.1%}")
    for f in mt.FEATURES:
        r, p = backtest(events, stats, "ret24h", only=(f,))
        reported[f"ret24h_{f}_only"] = {"rho": round(r, 3), "percentile": round(p, 3)}
        print(f"Reported ret24h, {f} only: rho={r:.3f} percentile={p:.1%}")
    winners = sum(1 for e in events if e["outcomes"]["ret24h_pct"] > 0)
    print(f"Winners at 24 h: {winners} of {len(events)}")
    corpus["backtest"] = {"verdict": verdict, "ret24h": {"rho": round(rho, 3), "percentile": round(pct, 3)},
                          "reported": reported, "events": len(events), "winners_24h": winners,
                          "run_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    mt.CORPUS_FILE.write_text(json.dumps(corpus, indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "analyze":
        analyze()
    else:
        client = NansenClient()
        b = Budget(client)
        {"collect": collect, "outcomes": outcomes}[cmd](client, b)
        print(f"Corpus spend so far: {b.spent()} credits")
