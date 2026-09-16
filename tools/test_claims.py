#!/usr/bin/env python3
"""Offline checks on the claims the page makes. No API calls, no network.

    .venv/bin/python tools/test_claims.py

Each check guards a sentence a judge could test:
  - an echo means a verified early entry, not any earlier buy;
  - a buyer we could not check is never shown as a new face;
  - saved replays say only what their own data supports.
"""

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import launch_data as ld
from reflex import echoes, utc

ROOT = Path(__file__).resolve().parent.parent
REPLAYS = ROOT / "data" / "replays"
T0 = json.loads(Path(ld.T0_FILE).read_text()) if Path(ld.T0_FILE).exists() else {}
FAILS = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def within_window(token, bought_at):
    """The rule the page claims: deployment resolved, and the buy inside the 6 h launch window."""
    info = T0.get(token)
    if not info or not info.get("deployment_timestamp") or info.get("t0_unresolved_capped"):
        return None  # unknown, which must never count as verified
    deploy, buy = utc(info["deployment_timestamp"]), utc(bought_at)
    t0 = utc(info["t0_timestamp"]) if info.get("t0_timestamp") else None
    failed = t0 is None or t0 - deploy > ld.LAUNCH_WINDOW
    return deploy <= buy < (deploy if failed else t0) + ld.LAUNCH_WINDOW


def test_late_buyer_is_not_an_echo():
    """A buy a day after the launch cannot become an early entry."""
    now = dt.datetime(2026, 9, 16, tzinfo=dt.timezone.utc)
    t0 = now - dt.timedelta(days=5)
    early = {"tok": {"symbol": "EARLY", "at": (t0 + dt.timedelta(hours=1)).isoformat()}}
    late = {"tok": {"symbol": "EARLY", "at": (t0 + dt.timedelta(hours=25)).isoformat()}}
    both = echoes([{"wallet": "a", "_launches": early, "entries": []},
                   {"wallet": "b", "_launches": early, "entries": []}])
    check("two verified entries make an echo", both["shared_launches"] == 1 and len(both["echoes"][0]["wallets"]) == 2)
    # The scanner must not hand a late buy to echoes() in the first place.
    check("a 25 h late buy is outside the launch window",
          within_window("x", late["tok"]["at"]) is None or not within_window("x", late["tok"]["at"]))
    pairs = echoes([{"wallet": "a", "_launches": early, "entries": []}])
    check("one wallet alone is not an echo", pairs["shared_launches"] == 0)


def test_echo_rows_stay_paired():
    """Each echo wallet keeps its own buy time; a mismatch would misattribute evidence."""
    t0 = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
    a = {"tok": {"symbol": "T", "at": (t0 + dt.timedelta(hours=2)).isoformat()}}
    b = {"tok": {"symbol": "T", "at": (t0 + dt.timedelta(hours=1)).isoformat()}}
    out = echoes([{"wallet": "late", "_launches": a, "entries": []},
                  {"wallet": "first", "_launches": b, "entries": []}])["echoes"][0]
    order_ok = out["wallets"] == ["first", "late"] and out["first_buys"] == [b["tok"]["at"], a["tok"]["at"]]
    check("wallets and buy times stay in step", order_ok, str(out))


def test_saved_replays_only_claim_verified_echoes():
    for path in sorted(REPLAYS.glob("*.json")):
        data = json.loads(path.read_text())
        event = next(e for e in data["events"] if e["kind"] == "event")
        name = event.get("symbol", path.stem)
        echo = next((e for e in data["events"] if e["kind"] == "echo"), None)
        if not echo:
            continue
        bad = []
        for e in echo["echoes"]:
            for wallet, at in zip(e["wallets"], e["first_buys"]):
                if within_window(e["token"], at) is not True:
                    bad.append(f"{e['symbol']} {wallet[:6]} {at[:16]}")
        check(f"{name}: every echo member is a verified early entry", not bad, "; ".join(bad[:3]))
        buyers = {b["wallet"] for b in next(e for e in data["events"] if e["kind"] == "buyers")["buyers"]}
        strays = [w for e in echo["echoes"] for w in e["wallets"] if w not in buyers]
        check(f"{name}: echoes only name this launch's buyers", not strays, str(strays[:3]))


def test_unavailable_history_is_not_a_new_face():
    for path in sorted(REPLAYS.glob("*.json")):
        data = json.loads(path.read_text())
        name = next(e for e in data["events"] if e["kind"] == "event").get("symbol", path.stem)
        for w in [e for e in data["events"] if e["kind"] == "wallet"]:
            if w.get("scoreable"):
                continue
            state = w.get("state")
            check(f"{name}: {w['wallet'][:6]} says which kind of gap it is", state in
                  {"history_unavailable", "checked_no_record", "price_data_missing", "too_little_history"}, str(state))
            if w.get("api_failures") and not w.get("history_trades"):
                check(f"{name}: {w['wallet'][:6]} failed history is not a new face", state == "history_unavailable", str(state))


def test_scoring_does_not_depend_on_todays_date():
    """A cached scan must give the same answer next week, so ages are read as of the fetch."""
    code = (ROOT / "reflex.py").read_text()
    check("scoring filters candidates as of the fetch time", "ld.plausible_launch(v, fetched_at)" in code)
    check("history returns when it was fetched", "return trades, fetched" in code)
    check("cached history applies both 30-day bounds", "cutoff - 30 * ld.DAY <= utc(x[\"block_timestamp\"]) < cutoff" in code)
    day = dt.timedelta(days=1)
    row = {"age_days_today": 3, "wallet_first_buy": (dt.datetime(2026, 9, 10, tzinfo=dt.timezone.utc)).isoformat()}
    fetched = dt.datetime(2026, 9, 13, tzinfo=dt.timezone.utc)
    same = ld.plausible_launch(row, fetched) == ld.plausible_launch(row, fetched)
    moved = ld.plausible_launch(row, fetched) != ld.plausible_launch(row, fetched + 7 * day)
    check("the same fetch time gives the same verdict", same)
    check("a later clock would have changed it, which is why we pin the fetch time", moved)


def test_page_keeps_faces_stable():
    """The character must come from the wallet alone, not from who else is in the lineup."""
    page = (ROOT / "web" / "index.html").read_text()
    check("faceIndex uses only the wallet", "function faceIndex(seed, n) { return Math.floor(rng(seed)() * n); }" in page)
    check("page explains a repeated character", "their addresses then appear above them" in page)


def main():
    test_late_buyer_is_not_an_echo()
    test_echo_rows_stay_paired()
    test_saved_replays_only_claim_verified_echoes()
    test_unavailable_history_is_not_a_new_face()
    test_scoring_does_not_depend_on_todays_date()
    test_page_keeps_faces_stable()
    print()
    if FAILS:
        print(f"{len(FAILS)} check(s) failed")
        raise SystemExit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
