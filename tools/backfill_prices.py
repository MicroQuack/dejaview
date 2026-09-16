#!/usr/bin/env python3
"""Add the first hour's price line to saved replays. One API call per launch.

    .venv/bin/python tools/backfill_prices.py [--write]
"""

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import launch_data as ld
from nansen_client import NansenClient
from reflex import utc

REPLAYS = Path(__file__).resolve().parent.parent / "data" / "replays"


def main():
    write = "--write" in sys.argv
    c = NansenClient()
    start = c.successful_calls
    for path in sorted(REPLAYS.glob("*.json")):
        data = json.loads(path.read_text())
        event = next(e for e in data["events"] if e["kind"] == "event")
        buyers = next(e for e in data["events"] if e["kind"] == "buyers")
        if buyers["tape"].get("price_s_usd"):
            print(f"{event.get('symbol')}: already has a price line")
            continue
        t0 = utc(event["t0"])
        series = ld.price_minutes(c, event["token"], t0, t0 + dt.timedelta(hours=1), f"backfill:price:{event['token'][:6]}")
        if not series:
            print(f"{event.get('symbol')}: no price returned, left alone")
            continue
        first, last = series[0][1], series[-1][1]
        print(f"{event.get('symbol')}: {len(series)} minutes, {round(100 * (last / first - 1)):+}% across the hour")
        if write:
            buyers["tape"]["price_s_usd"] = series
            path.write_text(json.dumps(data))
    print(("written" if write else "dry run: pass --write to save") + f". {c.successful_calls - start} calls used.")


if __name__ == "__main__":
    main()
