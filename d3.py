#!/usr/bin/env python3
"""Test D3: wide retest of Launch Reflex.

Rules are frozen in docs/D3_RETEST_PLAN.md (version 2). This file implements them.

    .venv/bin/python d3.py stage1    # sample events and actors
    .venv/bin/python d3.py stage3    # wallet history, merge, spend gate
    .venv/bin/python d3.py stage4    # launch entries and prices (only if the gate passed)
    .venv/bin/python d3.py analyze   # tests and verdict, no credits

State lives in spike_out/d3/. Every stage resumes from its saved state.
"""

import datetime as dt
import hashlib
import json
import math
import random
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor

import launch_data as ld
from nansen_client import OUT, NansenClient, rows, utc

D3 = OUT / "d3"
D3.mkdir(exist_ok=True)
DATES = ["2026-06-10", "2026-06-17", "2026-06-24", "2026-07-01", "2026-07-08",
         "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12"]
EXTRA_DATES = ["2026-06-13", "2026-06-20", "2026-06-27", "2026-07-04", "2026-07-11",
               "2026-07-18", "2026-07-25", "2026-08-01", "2026-08-08", "2026-08-15"]  # Amendment 1
TARGET_ACTORS = 40
CAP = 6000
SEED = 20260914
SHUFFLES = 5000
EXCLUDE_LABELS = ("pool", "router", "program", "exchange", "jupiter", "raydium", "meteora",
                  "pump", "binance", "coinbase", "okx", "bybit")
LN10 = math.log(10)


def load(name, default):
    p = D3 / name
    return json.loads(p.read_text()) if p.exists() else default


def save(name, data):
    (D3 / name).write_text(json.dumps(data, indent=2, default=str))


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


class Budget:
    """Tracks spend against the D3 start balance using the credit header."""

    def __init__(self, c):
        self.c = c
        state = load("state.json", {})
        if "start_balance" not in state:
            # Last balance the ledger saw before D3 started.
            for line in reversed(c.ledger_path.read_text().splitlines()):
                left = json.loads(line).get("headers", {}).get("x-nansen-credits-remaining")
                if left is not None:
                    state["start_balance"] = int(left)
                    break
            save("state.json", state)
        self.start = state["start_balance"]
        self.last_left = None

    def spent(self):
        # Error responses often carry no credit header, so keep the last known balance.
        left = self.c.last_headers.get("x-nansen-credits-remaining")
        if left is not None:
            self.last_left = int(left)
        if self.last_left is None:
            for line in reversed(self.c.ledger_path.read_text().splitlines()):
                v = json.loads(line).get("headers", {}).get("x-nansen-credits-remaining")
                if v is not None:
                    self.last_left = int(v)
                    break
        return self.start - self.last_left if self.last_left is not None else 0

    def ok(self, reserve=0):
        return self.spent() + reserve <= CAP


# --------------------------------------------------------------------------- Stage 1 and 2

def screener(c, date):
    cached = load(f"screener_{date}.json", None)
    if cached is not None:
        return cached
    day = dt.date.fromisoformat(date)
    out, capped = [], False
    for page in range(1, 5):
        resp = c.post("/api/v1beta1/token-screener/historical", {
            "chains": ["solana"],
            "to_date": (day + dt.timedelta(days=1)).isoformat(),
            "timeframe_days": 1,
            "apply_blacklist_filter": False,
            "filters": {"token_age_days": {"max": 1}, "volume_usd": {"min": 5000}},
            "order_by": [{"field": "token_age_days", "direction": "ASC"}],
            "pagination": {"page": page, "per_page": 1000},
        }, f"D3:screener:{date}:p{page}")
        if resp is None:
            sys.exit(f"Screener request failed for {date}; rerun stage1 to resume.")
        out += rows(resp)
        if (resp.get("pagination") or {}).get("is_last_page") or len(rows(resp)) < 1000:
            break
        capped = page == 4
    result = {"date": date, "tokens": out, "capped": capped}
    save(f"screener_{date}.json", result)
    return result


def candidates(scr):
    toks = {t["token_address"] for t in scr["tokens"] if str(t.get("token_address", "")).endswith("pump")}
    return sorted(toks, key=lambda t: sha(t + scr["date"]))


def first_hour_actors(c, token, deploy, t0, used):
    m = dt.timedelta(minutes=1)
    windows = [(deploy, t0 + 5 * m), (t0 + 5 * m, t0 + 15 * m), (t0 + 15 * m, t0 + 30 * m), (t0 + 30 * m, t0 + 60 * m)]
    buys = []
    for i, (a, b) in enumerate(windows):
        resp = c.post("/api/v1/tgm/dex-trades", {
            "chain": "solana", "token_address": token,
            "date": {"from": ld.iso(a), "to": ld.iso(b)},
            "filters": {"action": "BUY", "estimated_value_usd": {"min": 500}},
            "order_by": [{"field": "estimated_value_usd", "direction": "DESC"}],
            "pagination": {"page": 1, "per_page": 1000},
        }, f"D3:actors:{token[:6]}:w{i}")
        if resp is None:
            return None
        buys += rows(resp)
    seen, wallets = set(), {}
    for x in buys:
        k = (x["transaction_hash"], x["trader_address"], x["token_amount"])
        if k in seen:
            continue  # window edges are inclusive
        seen.add(k)
        w = x["trader_address"]
        e = wallets.setdefault(w, {"wallet": w, "usd": 0.0, "buys": 0, "first_buy": x["block_timestamp"],
                                   "label": x.get("trader_address_label") or ""})
        e["usd"] += float(x.get("estimated_value_usd") or 0)
        e["buys"] += 1
        e["first_buy"] = min(e["first_buy"], x["block_timestamp"])
    keep = [e for w, e in wallets.items()
            if not any(k in e["label"].lower() for k in EXCLUDE_LABELS)
            and e["buys"] <= 25 and w not in used]
    keep.sort(key=lambda e: -e["usd"])
    return keep


def stage1(c, budget, dates=DATES):
    t0_cache = ld.JsonCache(ld.T0_FILE)
    events = load("events.json", {})
    used = {a["wallet"] for ev in events.values() for a in ev["actors"]}
    for n, date in enumerate(dates):
        if date in events:
            continue
        scr = screener(c, date)
        cands = candidates(scr)
        print(f"{date}: {len(scr['tokens'])} screener tokens, {len(cands)} pump.fun, capped={scr['capped']}")
        day = dt.date.fromisoformat(date)
        if dates is DATES and n == 0 and not load("state.json", {}).get("validated"):
            good = 0
            for t in cands[:5]:
                d = None
                for _ in range(3):  # a request failure is not evidence either way
                    info = c.post("/api/v1/tgm/token-information",
                                  {"chain": "solana", "token_address": t, "timeframe": "1d"},
                                  f"D3:validate:{t[:6]}")
                    if info is not None:
                        d = ((info.get("data") or {}).get("token_details") or {}).get("token_deployment_date")
                        break
                if d and abs((utc(d).date() - day).days) <= 1:
                    good += 1
            print(f"  validation: {good} of 5 deployed within a day of {date}")
            if good < 4:
                sys.exit("STOP: the historical screener is not point-in-time. D3 halted per the rules.")
            state = load("state.json", {})
            state["validated"] = True
            save("state.json", state)
        event, skipped = None, []
        for t in cands[:15]:
            if not budget.ok(200):
                sys.exit("STOP: budget reached during Stage 1.")
            info = None
            for _ in range(3):
                info = ld.resolve_t0(c, t, t0_cache)
                if info is not None:
                    break
            if info is None:
                skipped.append(t)  # API failure after retries; logged so the bias is visible
                continue
            if not info.get("deployment_timestamp") or not info.get("t0_timestamp"):
                continue
            deploy, t0 = utc(info["deployment_timestamp"]), utc(info["t0_timestamp"])
            if deploy.date() != day or t0 - deploy > ld.LAUNCH_WINDOW:
                continue
            actors = None
            for _ in range(3):
                actors = first_hour_actors(c, t, deploy, t0, used)
                if actors is not None:
                    break
            if actors is None:
                skipped.append(t)
                continue
            if len(actors) < 6:
                continue
            event = {"date": date, "token": t, "symbol": info.get("symbol"),
                     "deployment": deploy.isoformat(), "t0": t0.isoformat(), "actors": actors[:12],
                     "screener_capped": scr["capped"], "skipped_for_api_failure": skipped}
            break
        t0_cache.save()
        events[date] = event or {"date": date, "token": None, "actors": [], "skipped_for_api_failure": skipped}
        used |= {a["wallet"] for a in (event or {}).get("actors", [])}
        save("events.json", events)
        print(f"  event: {event['symbol'] if event else None}  actors={len(event['actors']) if event else 0}  "
              f"spent so far {budget.spent()}")


# --------------------------------------------------------------------------- Stage 3

def stage3(c, budget):
    events = load("events.json", {})
    now = dt.datetime.now(dt.timezone.utc)
    (D3 / "history").mkdir(exist_ok=True)
    wallets = load("wallets.json", {})
    jobs = [(ev, a) for ev in events.values() if ev.get("token") for a in ev["actors"]
            if a["wallet"] not in wallets]

    def job(item):
        ev, a = item
        t0 = utc(ev["t0"])
        hist = []
        for lo, hi in ((t0 - 7 * ld.DAY, t0), (t0 - 14 * ld.DAY, t0 - 7 * ld.DAY), (t0 - 30 * ld.DAY, t0 - 14 * ld.DAY)):
            ok, r = ld.wallet_history(c, a["wallet"], lo, hi, f"D3:hist:{a['wallet'][:6]}")
            if not ok:
                return None
            hist += [x for x in r if utc(x["block_timestamp"]) < t0]
        (D3 / "history" / f"{a['wallet']}.json").write_text(json.dumps(hist))
        fb = ld.first_buys(hist)
        cands = {k: v for k, v in fb.items()
                 if ld.plausible_launch(v, now) and utc(v["wallet_first_buy"]) + ld.LAUNCH_WINDOW < t0}
        return a["wallet"], {"event": ev["date"], "t0": ev["t0"], "trades": len(hist), "candidates": cands}

    if jobs and not budget.ok(3 * len(jobs)):
        sys.exit("STOP: budget would be exceeded in Stage 3.")
    with ThreadPoolExecutor(8) as pool:
        for res in pool.map(job, jobs):
            if res:
                wallets[res[0]] = res[1]
    save("wallets.json", wallets)
    failed = len(jobs) - sum(1 for ev, a in jobs if a["wallet"] in wallets)
    if failed:
        print(f"{failed} wallet histories failed; rerun stage3 to retry.")

    passed = {w: v for w, v in wallets.items() if len(v["candidates"]) >= 20}
    print(f"Wallets with history: {len(wallets)}. Passed the 20-candidate gate: {len(passed)}.")

    # Merge same-operator wallets.
    parent = {w: w for w in passed}

    def find(w):
        while parent[w] != w:
            w = parent[w]
        return w

    ws = sorted(passed)
    for i, a in enumerate(ws):
        ca = passed[a]["candidates"]
        for b in ws[i + 1:]:
            cb = passed[b]["candidates"]
            same = sum(1 for t, v in cb.items() if t in ca and abs(
                (utc(v["wallet_first_buy"]) - utc(ca[t]["wallet_first_buy"])).total_seconds()) <= 5)
            if same >= 0.5 * min(len(ca), len(cb)):
                parent[find(b)] = find(a)
    groups = {}
    for w in ws:
        groups.setdefault(find(w), []).append(w)
    actors = {}
    for root, members in groups.items():
        first_event = min(members, key=lambda w: passed[w]["event"])
        cutoff = min(utc(passed[w]["t0"]) for w in members)
        merged = {}
        for w in members:
            for t, v in passed[w]["candidates"].items():
                if utc(v["wallet_first_buy"]) + ld.LAUNCH_WINDOW >= cutoff:
                    continue
                if t not in merged or v["wallet_first_buy"] < merged[t]["wallet_first_buy"]:
                    merged[t] = v
        if len(merged) >= 20:
            aid = sha("|".join(sorted(members)))[:12]
            actors[aid] = {"id": aid, "wallets": sorted(members), "event": passed[first_event]["event"],
                           "cutoff": cutoff.isoformat(), "candidates": merged}
    save("actors.json", actors)

    holders = {}
    for a in actors.values():
        for t in a["candidates"]:
            holders[t] = holders.get(t, 0) + 1
    pairs = sum(len(a["candidates"]) for a in actors.values())
    shared = sum(1 for a in actors.values() for t in a["candidates"] if holders[t] > 1)
    n_events = len({a["event"] for a in actors.values()})
    overlap = shared / pairs if pairs else 1.0
    gate = {"events": n_events, "actors": len(actors), "shared_pair_share": round(overlap, 3),
            "merged_groups": sum(1 for g in groups.values() if len(g) > 1),
            "pass": n_events >= 6 and len(actors) >= 30 and overlap <= 0.5,
            "spent_so_far": budget.spent()}
    state = load("state.json", {})
    state["gate"] = gate
    save("state.json", state)
    print("Spend gate:", gate)


# --------------------------------------------------------------------------- Stage 4

def expand(c, budget):
    """Amendment 1: add extra dates one at a time until 40 actors pass the gate."""
    for date in EXTRA_DATES:
        actors = load("actors.json", {})
        if len(actors) >= TARGET_ACTORS:
            break
        if date in load("events.json", {}):
            continue
        stage1(c, budget, dates=[date])
        stage3(c, budget)
    actors = load("actors.json", {})
    state = load("state.json", {})
    state["amendment1"] = {"actors": len(actors), "dates_added": [d for d in EXTRA_DATES if d in load("events.json", {})]}
    save("state.json", state)
    print("Amendment 1 finished:", state["amendment1"], "gate:", state.get("gate"))


def stage4(c, budget):
    state = load("state.json", {})
    if not (state.get("gate") or {}).get("pass"):
        sys.exit("Spend gate did not pass. Verdict: INCONCLUSIVE. Stage 4 does not run.")
    actors = load("actors.json", {})
    entries = load("entries.json", {})
    t0_cache = ld.JsonCache(ld.T0_FILE)
    market = ld.JsonCache(D3 / "market.json")
    order = sorted(actors, key=sha)
    for aid in order:
        if aid in entries:
            continue
        if not budget.ok(150):
            print(f"STOP: budget cap. Finished {len(entries)} of {len(actors)} actors.")
            break
        a = actors[aid]
        cands = sorted(a["candidates"].values(), key=lambda v: v["wallet_first_buy"], reverse=True)[:26]
        with ThreadPoolExecutor(8) as pool:
            infos = list(pool.map(lambda v: ld.resolve_t0(c, v["prior_token_address"], t0_cache), cands))
        t0_cache.save()
        launch = []
        for v, info in zip(cands, infos):
            if not info or not info.get("deployment_timestamp") or info.get("t0_unresolved_capped"):
                continue
            deploy, buy = utc(info["deployment_timestamp"]), utc(v["wallet_first_buy"])
            t0 = utc(info["t0_timestamp"]) if info.get("t0_timestamp") else None
            failed = t0 is None or t0 - deploy > ld.LAUNCH_WINDOW
            end = deploy + ld.LAUNCH_WINDOW if failed else t0 + ld.LAUNCH_WINDOW
            if deploy <= buy < end:
                launch.append({**v, "failed_launch": failed, "deployment": deploy.isoformat(),
                               "token_t0": None if failed else t0.isoformat()})
        launch = launch[:20]

        def price(e):
            key = f"{e['prior_token_address']}|{e['wallet_first_buy']}"
            got = market.get(key)
            if got is None:
                got = ld.market_points(c, e["prior_token_address"], utc(e["wallet_first_buy"]),
                                       f"D3:px:{e['prior_token_address'][:6]}")
                if got is not None:
                    market.put(key, got)
            return {**e, **(got or {"p0": None, "p15": None, "pmax": None, "error": True})}

        with ThreadPoolExecutor(8) as pool:
            priced = list(pool.map(price, launch))
        market.save()
        if any(e.get("error") for e in priced):
            print(f"  actor {aid}: some price requests failed; rerun stage4 to retry this actor.")
            continue
        entries[aid] = priced
        save("entries.json", entries)
        usable = sum(1 for e in priced if e.get("p0"))
        print(f"  actor {aid} ({len(a['wallets'])} wallet) launch entries={len(launch)} with P0={usable} "
              f"failed launches={sum(e['failed_launch'] for e in priced)}  spent {budget.spent()}")


# --------------------------------------------------------------------------- Stage 5

def capped_log(a, b):
    if not a or not b:
        return None
    return max(-LN10, min(LN10, math.log(a / b)))


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / (sx * sy) if sx and sy else 0.0


def halves(es):
    es = sorted(es, key=lambda e: e["wallet_first_buy"])
    k = math.ceil(len(es) / 2)
    return es[:k], es[k:]


def persistence(groups, metric, min_entries=2):
    """groups: list of entry lists. Returns (rho, percentile, n_actors)."""
    old, new = [], []
    for es in groups:
        es = [e for e in es if e.get(metric) is not None]
        if len(es) < min_entries:
            continue
        o, n = halves(es)
        if not o or not n:
            continue
        old.append(statistics.mean(e[metric] for e in o))
        new.append(statistics.mean(e[metric] for e in n))
    if len(old) < 5:
        return None, None, len(old)
    rho = spearman(old, new)
    rng = random.Random(SEED)
    below = 0
    shuffled = new[:]
    for _ in range(SHUFFLES):
        rng.shuffle(shuffled)
        below += spearman(old, shuffled) < rho
    return rho, below / SHUFFLES, len(old)


def spread(groups, metric):
    vals = [[e[metric] for e in es if e.get(metric) is not None] for es in groups]
    vals = [v for v in vals if v]
    if len(vals) < 5:
        return None, None
    real = statistics.pstdev([statistics.mean(v) for v in vals])
    pool = [x for v in vals for x in v]
    sizes = [len(v) for v in vals]
    rng = random.Random(SEED)
    below = 0
    for _ in range(SHUFFLES):
        rng.shuffle(pool)
        i, means = 0, []
        for n in sizes:
            means.append(statistics.mean(pool[i:i + n]))
            i += n
        below += statistics.pstdev(means) < real
    return real, below / SHUFFLES


def analyze():
    actors = load("actors.json", {})
    entries = load("entries.json", {})
    state = load("state.json", {})
    if not (state.get("gate") or {}).get("pass"):
        print("VERDICT: INCONCLUSIVE (spend gate failed)", state.get("gate"))
        return
    incl = {}
    for aid, es in entries.items():
        usable = []
        for e in es:
            if not e.get("p0"):
                continue
            usable.append({**e, "mfe60": capped_log(e.get("pmax"), e["p0"]),
                           "r15": capped_log(e.get("p15"), e["p0"]),
                           "runner60": None if not e.get("pmax") else float(e["pmax"] >= 2 * e["p0"])})
        if len(usable) >= 16:
            incl[aid] = usable
    events = {actors[a]["event"] for a in incl}
    print(f"Included actors: {len(incl)} from {len(events)} events "
          f"(priced actors {len(entries)}, gate {state['gate']})")
    if len(incl) < 30 or len(events) < 6:
        print("VERDICT: INCONCLUSIVE (fewer than 30 actors or 6 events)")
        return
    ids = sorted(incl)
    groups = [incl[a] for a in ids]

    rho, p1, n1 = persistence(groups, "mfe60")
    print(f"P1 persistence mfe60: rho={rho:.3f} percentile={p1:.1%} actors={n1}")
    for m in ("r15", "runner60"):
        r, p, n = persistence(groups, m)
        print(f"S{2 if m == 'r15' else 3} persistence {m}: rho={r:.3f} percentile={p:.1%} actors={n}")

    holders = {}
    for es in groups:
        for t in {e["prior_token_address"] for e in es}:
            holders[t] = holders.get(t, 0) + 1
    unique = [[e for e in es if holders[e["prior_token_address"]] == 1] for es in groups]
    unique8 = [u for u in unique if sum(1 for e in u if e.get("mfe60") is not None) >= 8]
    s1_sd, s1 = spread(unique8, "mfe60")
    print(f"S1 spread on unique tokens: actors={len(unique8)} sd={s1_sd} percentile={s1}")

    loo = []
    for ev in sorted(events):
        g = [incl[a] for a in ids if actors[a]["event"] != ev]
        loo.append(persistence(g, "mfe60")[1])
    r1 = sum(1 for p in loo if p is not None and p >= 0.90) / len(loo) >= 0.80
    dropped = []
    for es in groups:
        best = max((e for e in es if e.get("mfe60") is not None), key=lambda e: e["mfe60"])
        dropped.append([e for e in es if e is not best])
    p_r2 = persistence(dropped, "mfe60")[1]
    r2 = p_r2 is not None and p_r2 >= 0.90
    _, p_r3, n_r3 = persistence(unique8, "mfe60")
    r3_evaluable = n_r3 >= 15
    r3 = (not r3_evaluable) or (p_r3 is not None and p_r3 >= 0.80)
    print(f"R1 leave-one-event-out percentiles: {[None if p is None else round(p, 3) for p in loo]} -> {'pass' if r1 else 'fail'}")
    print(f"R2 drop best entry: {p_r2} -> {'pass' if r2 else 'fail'}")
    print(f"R3 unique tokens: actors={n_r3} percentile={p_r3} evaluable={r3_evaluable} -> {'pass' if r3 else 'fail'}")

    ranked = sorted(groups, key=lambda es: -statistics.mean(
        e["mfe60"] for e in halves([x for x in es if x.get("mfe60") is not None])[0]))
    top, bottom = ranked[:5], ranked[-5:]

    def newer(gs, m):
        return [e[m] for es in gs for e in halves([x for x in es if x.get("mfe60") is not None])[1] if e.get(m) is not None]

    k1 = statistics.median(newer(top, "mfe60")) > statistics.median(newer(bottom, "mfe60"))
    k2 = statistics.mean(newer(top, "runner60")) > statistics.mean(newer(bottom, "runner60"))
    print(f"K1 top-5 newer median mfe60 {statistics.median(newer(top, 'mfe60')):+.2f} vs bottom-5 "
          f"{statistics.median(newer(bottom, 'mfe60')):+.2f} -> {k1}")
    print(f"K2 top-5 newer runner rate {statistics.mean(newer(top, 'runner60')):.0%} vs bottom-5 "
          f"{statistics.mean(newer(bottom, 'runner60')):.0%} -> {k2}")
    fl = [e["failed_launch"] for es in groups for e in es]
    print(f"Failed launches among included entries: {sum(fl)} of {len(fl)}")

    if p1 >= 0.95 and rho >= 0.25 and r1 and r2 and r3 and k1 and k2:
        verdict = "PASS"
    elif p1 >= 0.90:
        verdict = "PROMISING"
    elif s1 is not None and s1 >= 0.95:
        verdict = "PROMISING (S1 route)"
    else:
        verdict = "FAIL"
    print(f"\nVERDICT: {verdict}")
    state["verdict"] = verdict
    save("state.json", state)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    if cmd == "analyze":
        analyze()
    else:
        client = NansenClient()
        b = Budget(client)
        {"stage1": stage1, "stage3": stage3, "expand": expand, "stage4": stage4}[cmd](client, b)
        print(f"D3 spend so far: {b.spent()} credits")
