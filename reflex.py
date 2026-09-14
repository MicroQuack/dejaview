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


def confidence(n):
    return "HIGH" if n >= 16 else "MEDIUM" if n >= 8 else "LOW" if n >= 3 else None


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
            raise ValueError("Nansen has no deployment record for this token on Solana.")
        if not info.get("t0_timestamp"):
            raise ValueError("This token never reached $5,000 of DEX volume, so it has no launch moment.")
        return info

    def first_hour_buys(self, token, deploy, t0, now):
        """Every buyer after the filters, largest first, with buy USD per first-hour window."""
        m = dt.timedelta(minutes=1)
        edges = [deploy, t0 + 5 * m, t0 + 15 * m, t0 + 30 * m, t0 + 60 * m]
        buys = []
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
            buys += [(i, x) for x in rows(resp)]
        seen, wallets = set(), {}
        for i, x in buys:  # window order, so a buy on a shared edge counts in the earlier window
            k = (x["transaction_hash"], x["trader_address"], x["token_amount"])
            if k in seen:
                continue
            seen.add(k)
            w = x["trader_address"]
            e = wallets.setdefault(w, {"wallet": w, "usd": 0.0, "buys": 0, "first_buy": x["block_timestamp"],
                                       "label": x.get("trader_address_label") or "", "window_usd": [0.0] * 4})
            usd = float(x.get("estimated_value_usd") or 0)
            e["usd"] += usd
            e["window_usd"][i] += usd
            e["buys"] += 1
            e["first_buy"] = min(e["first_buy"], x["block_timestamp"])
        keep = [e for e in wallets.values()
                if not any(k in e["label"].lower() for k in EXCLUDE_LABELS) and e["buys"] <= 25]
        keep.sort(key=lambda e: -e["usd"])
        for e in keep:
            e["entry_delay_s"] = (utc(e["first_buy"]) - t0).total_seconds()
        return keep

    def first_hour_buyers(self, token, deploy, t0, now):
        return self.first_hour_buys(token, deploy, t0, now)[:MAX_BUYERS]

    # ------------------------------------------------------------------ wallet

    def history(self, wallet, cutoff):
        """Wallet trades in the 30 days before cutoff. Cached; filtered strictly before cutoff."""
        path = HISTORY_DIR / f"{wallet}.json"
        if path.exists():
            cached = json.loads(path.read_text())
            if utc(cached["from"]) <= cutoff - 30 * ld.DAY and utc(cached["to"]) >= cutoff:
                return [x for x in cached["trades"] if utc(x["block_timestamp"]) < cutoff]
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
                return None
            trades += [x for x in r if utc(x["block_timestamp"]) < cutoff]
        path.write_text(json.dumps({"from": (cutoff - 30 * ld.DAY).isoformat(), "to": cutoff.isoformat(),
                                    "trades": trades}))
        return trades

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
        now = dt.datetime.now(dt.timezone.utc)
        hist = self.history(wallet, cutoff)
        if hist is None:
            return {**buyer, "scoreable": False, "api_failures": 1,
                    "reason": "Nansen did not return this wallet's history."}
        cands = [v for v in ld.first_buys(hist).values()
                 if ld.plausible_launch(v, now) and utc(v["wallet_first_buy"]) + ld.LAUNCH_WINDOW < cutoff]
        cands.sort(key=lambda v: v["wallet_first_buy"], reverse=True)
        cands = cands[:CANDIDATE_POOL]
        with ThreadPoolExecutor(4) as pool:
            infos = list(pool.map(lambda v: ld.resolve_t0(self.c, v["prior_token_address"], self.t0_cache), cands))
        failures = sum(1 for info in infos if info is None)
        entries = []
        for v, info in zip(cands, infos):
            if not info or not info.get("deployment_timestamp") or info.get("t0_unresolved_capped"):
                continue
            deploy, buy = utc(info["deployment_timestamp"]), utc(v["wallet_first_buy"])
            t0 = utc(info["t0_timestamp"]) if info.get("t0_timestamp") else None
            failed = t0 is None or t0 - deploy > ld.LAUNCH_WINDOW
            if deploy <= buy < (deploy if failed else t0) + ld.LAUNCH_WINDOW:
                entries.append({**v, "failed_launch": failed})
        entries = entries[:MAX_ENTRIES]
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
        result = {**buyer, "history_trades": len(hist), "launch_candidates": len(cands), "api_failures": failures,
                  "entries": sorted(scored, key=lambda s: s["bought_at"], reverse=True)}
        conf = confidence(n)
        if conf is None:
            return {**result, "scoreable": False,
                    "reason": ("No prior launch entries with price data in the 30 days before this launch." if n == 0
                               else f"Only {n} prior launch entries with price data in the 30 days before this launch.")}
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
                 "validated_launchpad": token.endswith("pump")}
        self.emit("event", **event)
        all_buyers = self.first_hour_buys(token, deploy, t0, now)
        buyers = all_buyers[:MAX_BUYERS]
        self.emit("buyers", buyers=buyers)
        self.emit("stage", key="history", text="Checking prior launch behaviour")
        results = []
        with ThreadPoolExecutor(4) as pool:
            for res in pool.map(lambda b: self.score_wallet(b, t0), buyers):
                results.append(res)
                self.emit("wallet", **res)
        self.t0_cache.save()
        self.market.save()
        scoreable = [r for r in results if r["scoreable"]]
        deja = self.match(token, event, all_buyers, results)
        summary = {**event, "buyers": len(results), "scoreable": len(scoreable),
                   "above_average": sum(1 for r in scoreable if r["reflex"] >= 60),
                   "api_calls": self.c.successful_calls - calls_start}
        self.emit("done", **summary)
        return {"event": summary, "wallets": results, "deja_view": deja}

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
                           corpus_events=len(corpus["events"]))
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
