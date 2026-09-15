#!/usr/bin/env python3
"""Summarize Nansen API usage from spike_out/calls.jsonl for the competition.

    .venv/bin/python tools/api_usage.py

Counts rows, not the running total in each row. The running total is wrong when
two processes write to the ledger at the same time.
"""

import collections
import json
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "spike_out" / "calls.jsonl"


def main():
    if not LEDGER.exists():
        raise SystemExit(f"No call log at {LEDGER}. Run a scan first.")
    total = ok = 0
    credits = 0.0
    first = last = None
    by_endpoint = collections.defaultdict(lambda: [0, 0, 0.0])  # requests, successful, credits
    for line in LEDGER.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        first = first or row["ts"]
        last = row["ts"]
        entry = by_endpoint[row["path"]]
        entry[0] += 1
        if row.get("status") == 200 and not row.get("error"):
            ok += 1
            entry[1] += 1
            cost = row.get("credits_header") or (row.get("headers") or {}).get("x-nansen-credits-used")
            try:
                credits += float(cost)
                entry[2] += float(cost)
            except (TypeError, ValueError):
                pass
    print("Déjà View: Nansen API usage")
    print(f"  Requests:            {total:,}")
    print(f"  Successful requests: {ok:,}")
    print(f"  Credits charged:     {credits:,.0f}")
    print(f"  First request:       {first}")
    print(f"  Last request:        {last}")
    print("\n  Endpoint                                         Requests  Successful   Credits")
    for path, (n, good, cr) in sorted(by_endpoint.items(), key=lambda kv: -kv[1][0]):
        print(f"  {path:<48} {n:>8,}  {good:>10,}  {cr:>8,.0f}")


if __name__ == "__main__":
    main()
