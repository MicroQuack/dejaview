"""Launch Reflex scoring service.

scan(token) finds a launch's meaningful first-hour buyers and scores each one on
its prior launch entries. Rules come from the validated spike (spike_results.md,
Test D3):

- T0: first time cumulative DEX volume reaches $5,000.
- Buyers: buys of at least $500 in the first hour after T0, largest total first.
- Launch entry: first buy within 6 h of T0, or of deployment for a failed launch.
- Outcome: mfe60, the capped log return from the entry-minute market price to the
  5th-highest price in the following hour.
- Reflex: shrunk mean mfe60, shown as a percentile of the D3 reference buyers.
- Point in time: only trades and outcomes known before the event's T0 count.
"""

import datetime as dt
import json
import math
import statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import launch_data as ld
import matching as mt
from nansen_client import OUT, NansenClient, rows, utc

ROOT = Path(__file__).resolve().parent
REFERENCE = mt.REFERENCE
LN10 = math.log(10)
MIN_BUY_USD = 500
MAX_BUYERS = 8
MAX_ENTRIES = 16
CANDIDATE_POOL = 22
EXCLUDE_LABELS = ("pool", "router", "program", "exchange", "jupiter", "raydium", "meteora",
                  "pump", "binance", "coinbase", "okx", "bybit")
HISTORY_DIR = OUT / "wallet_history_cache"


def capped_log(a, b):
    return max(-LN10, min(LN10, math.log(a / b))) if a and b else None


percentile = mt.percentile


def describe(pct):
    if pct >= 80:
        return "Historically well above other launch buyers at getting into strong first-hour launches."
    if pct >= 60:
        return "Historically above average at getting into strong first-hour launches."
    if pct >= 40:
        return "A typical launch buyer."
    if pct >= 20:
        return "Historically below average at getting into strong first-hour launches."
    return "Historically well below other launch buyers."


def plural(n, one, many):
    return one if n == 1 else many


def confidence(n):
    return "HIGH" if n >= 16 else "MEDIUM" if n >= 8 else "LOW" if n >= 3 else None


def tape(all_buyers, deploy, t0):
    """Buy USD per minute from deployment to T0 + 1 h, across every filtered buyer, for the replay's volume band."""
    start = (deploy - t0).total_seconds()
    minutes = int((3600 - start) // 60) + 1
    usd = [0] * minutes
    for b in all_buyers:
        for sec, amount in b["buy_list"]:
            i = int((sec - start) // 60)
            if 0 <= i < minutes:
                usd[i] += amount
    return {"start_s": round(start), "minute_usd": usd}


def echoes(results, top=6):
    """Earlier launches that two or more of this launch's top buyers were also early on.

    A launch counts for a wallet only when that launch's deployment and T0 resolved, the wallet's
    first buy fell inside the 6 h launch window, and the window closed at least 6 h before this
    launch's T0. Launches we could not verify are left out, not counted. Moves come from the priced
    entries used for Launch Reflex, so verified but unpriced launches have no move.
    """
    holders, moves = {}, {}
    for r in results:
        for tok, v in (r.get("_launches") or {}).items():
            holders.setdefault(tok, []).append((r["wallet"], v))
        for e in r.get("entries", []):
            moves.setdefault(e["token"], []).append(e["mfe60"])
    shared = []
    for tok, hs in holders.items():
        if len(hs) < 2:
            continue
        mv = moves.get(tok)
        hs = sorted(hs, key=lambda h: h[1]["at"])
        shared.append({"token": tok, "symbol": hs[0][1]["symbol"], "wallets": [w for w, _ in hs],
                       "first_buys": [v["at"] for _, v in hs],  # same order as wallets
                       "best_move_1h_pct": round(100 * (math.exp(max(mv)) - 1)) if mv else None})
    shared.sort(key=lambda s: s["first_buys"][-1], reverse=True)  # most recent first, then
    shared.sort(key=lambda s: (-len(s["wallets"]), s["best_move_1h_pct"] is None))  # biggest groups with a move
    sets = {r["wallet"]: set(r.get("_launches") or {}) for r in results}
    ws = [w for w, st in sets.items() if len(st) >= 10]
    together = []
    for i, a in enumerate(ws):
        for b in ws[i + 1:]:
            both = len(sets[a] & sets[b])
            if both >= 0.5 * min(len(sets[a]), len(sets[b])):
                together.append({"wallets": [a, b], "shared": both})
    return {"shared_launches": len(shared), "largest_group": len(shared[0]["wallets"]) if shared else 0,
            "echoes": shared[:top], "often_together": together}


class Scanner:
    def __init__(self, client=None, progress=None):
        self.c = client or NansenClient()
        self.t0_cache = ld.JsonCache(ld.T0_FILE)
        self.market = ld.JsonCache(OUT / "market_points.json")
        d3_market = OUT / "d3" / "market.json"  # prices already fetched by the D3 retest
        if d3_market.exists():
            for k, v in json.loads(d3_market.read_text()).items():
                self.market.data.setdefault(k, v)
        self.progress = progress or (lambda kind, data: None)
        HISTORY_DIR.mkdir(exist_ok=True)

    def emit(self, kind, **data):
        self.progress(kind, data)

    # ------------------------------------------------------------------ event

    def resolve_event(self, token):
        info = None
        for _ in range(3):
            info = ld.resolve_t0(self.c, token, self.t0_cache)
            if info is not None:
                break
        self.t0_cache.save()
        if not info or not info.get("deployment_timestamp"):
            raise ValueError("Nansen has no deployment record for this token on Solana. Check the address: "
                             "Solana addresses are case-sensitive, and pump.fun addresses end in \"pump\".")
        if not info.get("t0_timestamp"):
            raise ValueError("This token never reached $5,000 of DEX volume, so it has no launch moment.")
        return info

    def first_hour_buys(self, token, deploy, t0, now):
        """Every buyer after the filters, largest first, with buy USD per first-hour window."""
        m = dt.timedelta(minutes=1)
        edges = [deploy, t0 + 5 * m, t0 + 15 * m, t0 + 30 * m, t0 + 60 * m]
        buys, self.capped_windows = [], 0
        for i, (a, b) in enumerate(zip(edges, edges[1:])):
            if a >= now:
                break
            resp = None
            for _ in range(3):
                resp = self.c.post("/api/v1/tgm/dex-trades", {
                    "chain": "solana", "token_address": token,
                    "date": {"from": ld.iso(a), "to": ld.iso(min(b, now))},
                    "filters": {"action": "BUY", "estimated_value_usd": {"min": MIN_BUY_USD}},
                    "order_by": [{"field": "estimated_value_usd", "direction": "DESC"}],
                    "pagination": {"page": 1, "per_page": 1000},
                }, f"scan:buyers:{token[:6]}")
                if resp is not None:
                    break
            if resp is None:
                raise RuntimeError("Nansen did not return first-hour trades. Try again shortly.")
            page = rows(resp)
            if len(page) >= 1000:
                self.capped_windows += 1  # more trades exist than one page returns, so this window is partial
            buys += [(i, x) for x in page]
        seen, wallets = set(), {}
        for i, x in buys:  # window order, so a buy on a shared edge counts in the earlier window
            k = (x["transaction_hash"], x["trader_address"], x["token_amount"])
            if k in seen:
                continue
            seen.add(k)
            w = x["trader_address"]
            e = wallets.setdefault(w, {"wallet": w, "usd": 0.0, "buys": 0, "first_buy": x["block_timestamp"],
                                       "label": x.get("trader_address_label") or "", "window_usd": [0.0] * 4,
                                       "buy_list": []})
            usd = float(x.get("estimated_value_usd") or 0)
            e["buy_list"].append([round((utc(x["block_timestamp"]) - t0).total_seconds()), round(usd)])
            e["usd"] += usd
            e["window_usd"][i] += usd
            e["buys"] += 1
            e["first_buy"] = min(e["first_buy"], x["block_timestamp"])
        keep = [e for e in wallets.values()
                if not any(k in e["label"].lower() for k in EXCLUDE_LABELS) and e["buys"] <= 25]
        keep.sort(key=lambda e: -e["usd"])
        for e in keep:
            e["entry_delay_s"] = (utc(e["first_buy"]) - t0).total_seconds()
            e["buy_list"].sort()
        return keep

    def first_hour_buyers(self, token, deploy, t0, now):
        return self.first_hour_buys(token, deploy, t0, now)[:MAX_BUYERS]

    # ------------------------------------------------------------------ wallet

    def history(self, wallet, cutoff):
        """Wallet trades in the 30 days before cutoff, with when they were fetched.

        Returns (trades, fetched_at). Token ages in the rows were measured at fetch time, so scoring
        must use that moment, not today's date, or a cached scan changes as the calendar moves.
        """
        path = HISTORY_DIR / f"{wallet}.json"
        if path.exists():
            cached = json.loads(path.read_text())
            if utc(cached["from"]) <= cutoff - 30 * ld.DAY and utc(cached["to"]) >= cutoff:
                fetched = utc(cached["fetched_at"]) if cached.get("fetched_at") else \
                    dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
                window = [x for x in cached["trades"]
                          if cutoff - 30 * ld.DAY <= utc(x["block_timestamp"]) < cutoff]  # both bounds, not just the top
                return window, fetched
        trades = []
        for lo, hi in ((cutoff - 7 * ld.DAY, cutoff), (cutoff - 14 * ld.DAY, cutoff - 7 * ld.DAY),
                       (cutoff - 30 * ld.DAY, cutoff - 14 * ld.DAY)):
            r = None
            for _ in range(3):
                ok, r = ld.wallet_history(self.c, wallet, lo, hi, f"scan:hist:{wallet[:6]}")
                if ok:
                    break
                r = None
            if r is None:
                return None, None
            trades += [x for x in r if utc(x["block_timestamp"]) < cutoff]
        fetched = dt.datetime.now(dt.timezone.utc)
        path.write_text(json.dumps({"from": (cutoff - 30 * ld.DAY).isoformat(), "to": cutoff.isoformat(),
                                    "fetched_at": fetched.isoformat(), "trades": trades}))
        return trades, fetched

    def market_point(self, token, buy):
        key = f"{token}|{buy}"
        got = self.market.get(key)
        if got is None:
            for _ in range(3):
                got = ld.market_points(self.c, token, utc(buy), f"scan:px:{token[:6]}", with_p15=False)
                if got is not None:
                    self.market.put(key, got)
                    break
        return got

    def score_wallet(self, buyer, cutoff):
        wallet = buyer["wallet"]
        hist, fetched_at = self.history(wallet, cutoff)
        if hist is None:
            return {**buyer, "scoreable": False, "api_failures": 1, "state": "history_unavailable",
                    "reason": "Nansen did not return this wallet's history."}
        cands = [v for v in ld.first_buys(hist).values()
                 if ld.plausible_launch(v, fetched_at) and utc(v["wallet_first_buy"]) + ld.LAUNCH_WINDOW < cutoff]
        cands.sort(key=lambda v: v["wallet_first_buy"], reverse=True)
        cands = cands[:CANDIDATE_POOL]
        with ThreadPoolExecutor(4) as pool:
            infos = list(pool.map(lambda v: ld.resolve_t0(self.c, v["prior_token_address"], self.t0_cache), cands))
        failures = sum(1 for info in infos if info is None)
        verified, unverified = [], 0
        for v, info in zip(cands, infos):
            if not info or not info.get("deployment_timestamp") or info.get("t0_unresolved_capped"):
                unverified += 1  # we could not resolve the launch, so we cannot claim this wallet was early on it
                continue
            deploy, buy = utc(info["deployment_timestamp"]), utc(v["wallet_first_buy"])
            t0 = utc(info["t0_timestamp"]) if info.get("t0_timestamp") else None
            failed = t0 is None or t0 - deploy > ld.LAUNCH_WINDOW
            if deploy <= buy < (deploy if failed else t0) + ld.LAUNCH_WINDOW:
                verified.append({**v, "failed_launch": failed})
        entries = verified[:MAX_ENTRIES]
        with ThreadPoolExecutor(4) as pool:
            points = list(pool.map(lambda e: self.market_point(e["prior_token_address"], e["wallet_first_buy"]), entries))
        failures += sum(1 for p in points if p is None)
        scored = []
        for e, p in zip(entries, points):
            if p and p.get("p0") and p.get("pmax"):
                scored.append({"symbol": e["symbol"], "token": e["prior_token_address"],
                               "bought_at": e["wallet_first_buy"], "failed_launch": e["failed_launch"],
                               "mfe60": capped_log(p["pmax"], p["p0"]),
                               "reached_2x": p["pmax"] >= 2 * p["p0"]})
        n = len(scored)
        launches = {v["prior_token_address"]: {"symbol": v["symbol"], "at": v["wallet_first_buy"]}
                    for v in verified
                    if utc(v["wallet_first_buy"]) + ld.LAUNCH_WINDOW < cutoff}
        result = {**buyer, "_launches": launches, "history_trades": len(hist), "launch_candidates": len(cands),
                  "verified_launches": len(verified), "unverified_candidates": unverified, "api_failures": failures,
                  "entries": sorted(scored, key=lambda s: s["bought_at"], reverse=True)}
        conf = confidence(n)
        if conf is None:
            if n == 0 and not verified:
                state, reason = ("checked_no_record",
                                 "No launch in the 30 days before this one had a first buy inside its launch window.")
            elif n == 0:
                state, reason = ("price_data_missing",
                                 f"{len(verified)} earlier {plural(len(verified), 'launch', 'launches')} verified, "
                                 "but Nansen returned no first-hour price for them, so they cannot be scored.")
            else:
                state, reason = ("too_little_history",
                                 f"Only {n} priced launch {plural(n, 'entry', 'entries')} in the 30 days before this launch.")
            return {**result, "scoreable": False, "state": state, "reason": reason}
        k, prior = REFERENCE["shrinkage_k"], REFERENCE["prior_mean_mfe60"]
        shrunk = (sum(s["mfe60"] for s in scored) + k * prior) / (n + k)
        pct = percentile(shrunk)
        step = math.ceil(100 / len(REFERENCE["shrunk_mean_mfe60"]))  # finest rank the reference supports
        rank = f"TOP {max(step, 100 - pct)}%" if pct >= 50 else f"BOTTOM {max(step, pct)}%"
        return {**result, "scoreable": True, "reflex": pct, "reflex_raw": shrunk, "rank_label": rank,
                "confidence": conf, "prior_launch_entries": n,
                "runner_rate": sum(s["reached_2x"] for s in scored) / n,
                "failed_launch_rate": sum(s["failed_launch"] for s in scored) / n,
                "summary": describe(pct)}

    # ------------------------------------------------------------------ scan

    def scan(self, token):
        token = token.strip()
        now = dt.datetime.now(dt.timezone.utc)
        calls_start = self.c.successful_calls
        self.emit("stage", key="rewind", text="Rewinding onchain activity")
        info = self.resolve_event(token)
        deploy, t0 = utc(info["deployment_timestamp"]), utc(info["t0_timestamp"])
        event = {"token": token, "symbol": info.get("symbol"), "deployment": deploy.isoformat(),
                 "t0": t0.isoformat(), "first_hour_complete": now >= t0 + dt.timedelta(hours=1),
                 "observed_s": round(min(3600, (now - t0).total_seconds())),
                 "scanned_at": now.isoformat(),
                 "validated_launchpad": token.endswith("pump")}
        self.emit("event", **event)
        all_buyers = self.first_hour_buys(token, deploy, t0, now)
        buyers = all_buyers[:MAX_BUYERS]
        band = tape(all_buyers, deploy, t0)
        band["price_s_usd"] = ld.price_minutes(self.c, token, t0, min(now, t0 + dt.timedelta(hours=1)),
                                               f"scan:price:{token[:6]}")
        self.emit("buyers", buyers=buyers, tape=band,
                  capped_windows=getattr(self, "capped_windows", 0), qualifying_buyers=len(all_buyers))
        self.emit("stage", key="history", text="Checking prior launch behaviour")
        results = []
        with ThreadPoolExecutor(4) as pool:
            for res in pool.map(lambda b: self.score_wallet(b, t0), buyers):
                results.append(res)
                self.emit("wallet", **{k: v for k, v in res.items() if not k.startswith("_")})
        self.t0_cache.save()
        self.market.save()
        scoreable = [r for r in results if r["scoreable"]]
        self.emit("echo", **echoes(results))
        deja = self.match(token, event, all_buyers, results)
        summary = {**event, "buyers": len(results), "scoreable": len(scoreable),
                   "above_average": sum(1 for r in scoreable if r["reflex"] >= 60),
                   "api_calls": self.c.successful_calls - calls_start}
        self.emit("done", **summary)
        return {"event": summary, "wallets": [{k: v for k, v in r.items() if not k.startswith("_")} for r in results],
                "deja_view": deja}

    def match(self, token, event, all_buyers, results):
        """Fingerprint the launch and find similar past launches (docs/CORPUS_PLAN.md)."""
        self.emit("stage", key="match", text="Searching history")
        corpus = mt.load_corpus()
        out = {"fingerprint": None, "analogues": [], "seen_before": None, "reason": None,
               "backtest": (corpus or {}).get("backtest")}
        if not event["first_hour_complete"]:
            out["reason"] = "Similar launches appear one hour after the launch moment, when the first hour is complete."
        elif not results:
            out["reason"] = "No meaningful first-hour buyers."
        else:
            out["fingerprint"], out["reason"] = mt.fingerprint(all_buyers, results)
            if out["fingerprint"] and not (corpus and corpus.get("events")):
                out["reason"] = "The library of past launches has not been built yet."
            elif out["fingerprint"]:
                found = mt.analogues(out["fingerprint"], token, corpus)
                out.update(analogues=found["cards"], seen_before=found["seen_before"],
                           corpus_events=len(corpus["events"]),
                           fingerprint_rank=mt.corpus_rank(out["fingerprint"], corpus))
        self.emit("deja_view", **out)
        return out


if __name__ == "__main__":
    import sys

    def show(kind, data):
        if kind == "stage":
            print(f"... {data['text']}")
        elif kind == "event":
            print(f"{data['symbol']}  deployed {data['deployment']}  T0 {data['t0']}")
            if not data["validated_launchpad"]:
                print("  WARNING: not a pump.fun launch. Launch Reflex is validated on pump.fun launches only.")
        elif kind == "buyers":
            print(f"{len(data['buyers'])} meaningful first-hour buyers")
        elif kind == "wallet":
            w = data["wallet"]
            head = f"  {w[:4]}..{w[-4:]}  ${data['usd']:>9,.0f}  entered +{data['entry_delay_s'] / 60:.0f}m  "
            if data["scoreable"]:
                print(head + f"REFLEX {data['reflex']} ({data['rank_label']}) {data['confidence']}  "
                      f"{data['prior_launch_entries']} prior launches, {data['runner_rate']:.0%} reached 2x in 1h, "
                      f"{data['failed_launch_rate']:.0%} failed")
            else:
                print(head + f"not scoreable: {data['reason']}")
        elif kind == "deja_view":
            if data["fingerprint"]:
                print("fingerprint: " + ", ".join(mt.describe_feature(f, data["fingerprint"]) for f in mt.FEATURES)
                      + f" ({data['fingerprint']['scoreable_buyers']} known buyers)")
            if data["reason"]:
                print(f"similar launches: {data['reason']}")
            if data["seen_before"] is False:
                print("We haven't seen this one before. No close historical analogue yet; nearest shown for context.")
            for a in data["analogues"]:
                o = a["outcomes"]
                print(f"  {'counter-example ' if a['counter_example'] else ''}{a['symbol']} {a['date']} "
                      f"({a['closeness']}): 6h {o['ret6h_pct']:+.0f}%  24h {o['ret24h_pct']:+.0f}%  7d {o['ret7d_pct']:+.0f}%")
        elif kind == "done":
            print(f"{data['scoreable']} of {data['buyers']} scoreable, {data['above_average']} above average, "
                  f"{data['api_calls']} API calls")

    Scanner(progress=show).scan(sys.argv[1])
