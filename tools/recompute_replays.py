#!/usr/bin/env python3
"""Recompute echoes and evidence states in saved replays, from cached data only.

Echoes used to count any earlier token a buyer bought soon after deployment. They now count
only launches whose deployment and T0 resolved and whose 6 h launch window contained the buy.
Launch Reflex scores do not change, so this rewrites the echo event and the state of buyers
we could not score. Makes no API calls: a cache miss is reported, never guessed.

    .venv/bin/python tools/recompute_replays.py [--write]
"""

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import launch_data as ld
from reflex import HISTORY_DIR, echoes, utc

ROOT = Path(__file__).resolve().parent.parent
REPLAYS = ROOT / "data" / "replays"
T0_CACHE = json.loads(Path(ld.T0_FILE).read_text()) if Path(ld.T0_FILE).exists() else {}


def cached_history(wallet, cutoff):
    """Cached trades plus when they were fetched: token ages in the rows were measured then."""
    path = HISTORY_DIR / f"{wallet}.json"
    if not path.exists():
        return None, None
    cached = json.loads(path.read_text())
    if utc(cached["from"]) > cutoff - 30 * ld.DAY or utc(cached["to"]) < cutoff:
        return None, None
    fetched = utc(cached["fetched_at"]) if cached.get("fetched_at") else \
        dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    return [x for x in cached["trades"] if cutoff - 30 * ld.DAY <= utc(x["block_timestamp"]) < cutoff], fetched


def verified_launches(hist, cutoff, fetched_at):
    """Earlier launches this wallet was verifiably early on, plus what we could not verify."""
    found, unverified = {}, 0
    for v in ld.first_buys(hist).values():
        if not ld.plausible_launch(v, fetched_at) or utc(v["wallet_first_buy"]) + ld.LAUNCH_WINDOW >= cutoff:
            continue
        info = T0_CACHE.get(v["prior_token_address"])
        if not info or not info.get("deployment_timestamp") or info.get("t0_unresolved_capped"):
            unverified += 1
            continue
        deploy, buy = utc(info["deployment_timestamp"]), utc(v["wallet_first_buy"])
        t0 = utc(info["t0_timestamp"]) if info.get("t0_timestamp") else None
        failed = t0 is None or t0 - deploy > ld.LAUNCH_WINDOW
        if deploy <= buy < (deploy if failed else t0) + ld.LAUNCH_WINDOW:
            found[v["prior_token_address"]] = {"symbol": v["symbol"], "at": v["wallet_first_buy"]}
    return found, unverified


def state_for(w, hist, verified):
    if hist is None:
        return "history_unavailable"
    if not verified:
        return "checked_no_record"
    return "price_data_missing" if not w.get("entries") else "too_little_history"


def redo(path, write):
    data = json.loads(path.read_text())
    events = data["events"]
    event = next(e for e in events if e["kind"] == "event")
    cutoff = utc(event["t0"])
    results, misses = [], 0
    for w in [e for e in events if e["kind"] == "wallet"]:
        hist, fetched_at = cached_history(w["wallet"], cutoff)
        if hist is None:
            if not w.get("scoreable") and w.get("api_failures"):
                w["state"] = "history_unavailable"
            else:
                misses += 1
            results.append({**w, "_launches": {}})
            continue
        found, unverified = verified_launches(hist, cutoff, fetched_at)
        w["verified_launches"], w["unverified_candidates"] = len(found), unverified
        if not w.get("scoreable"):
            w["state"] = state_for(w, hist, found)
        results.append({**w, "_launches": found})
    fresh = echoes(results)
    old = next((e for e in events if e["kind"] == "echo"), None)
    before = old["echoes"][0] if old and old.get("echoes") else None
    after = fresh["echoes"][0] if fresh["echoes"] else None
    name = (event.get("symbol") or path.stem)[:14]
    print(f"{name:<14} shared launches {old['shared_launches'] if old else 0:>3} -> {fresh['shared_launches']:<3} "
          f"top echo {before['symbol'] if before else '-'} ({len(before['wallets']) if before else 0}) -> "
          f"{after['symbol'] if after else '-'} ({len(after['wallets']) if after else 0})"
          + (f"   [{misses} wallet histories not cached]" if misses else ""))
    if old:
        old.update({k: v for k, v in fresh.items()})
    if write:
        path.write_text(json.dumps(data))
    return misses


def main():
    write = "--write" in sys.argv
    misses = sum(redo(p, write) for p in sorted(REPLAYS.glob("*.json")))
    print("\n" + ("written" if write else "dry run: pass --write to save")
          + (f". {misses} wallets had no cached history, so their launches are left out." if misses else "."))


if __name__ == "__main__":
    main()
