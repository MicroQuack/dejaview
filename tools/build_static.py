#!/usr/bin/env python3
"""Build dist/: the public site as plain files, with no server and no API key.

The page falls back to these files when there is no local scan API, so the same
web/index.html runs locally against Python and publicly as a static site.

    .venv/bin/python tools/build_static.py
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
REPLAYS = ROOT / "data" / "replays"


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "replays").mkdir(parents=True)

    shutil.copy2(ROOT / "web" / "index.html", DIST / "index.html")
    shutil.copytree(ROOT / "web" / "art", DIST / "art",
                    ignore=shutil.ignore_patterns("raw", ".DS_Store"))

    index = []
    for path in sorted(REPLAYS.glob("*.json")):
        data = json.loads(path.read_text())
        event = next((e for e in data["events"] if e["kind"] == "event"), None)
        if not event:
            continue
        shutil.copy2(path, DIST / "replays" / path.name)
        index.append({"token": path.stem, "symbol": event.get("symbol"), "t0": event.get("t0"),
                      "saved_at": data.get("saved_at")})

    featured = "98kfF7rmsg1QDUEoCqNE7g7M1FdrTt92TEp2CLzypump"  # PAID: the launch a first-time visitor should meet
    index.sort(key=lambda r: r["t0"] or "", reverse=True)
    index.sort(key=lambda r: r["token"] != featured)
    (DIST / "replays" / "index.json").write_text(json.dumps({"public": True, "replays": index}))

    files = [p for p in DIST.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    print(f"dist/: {len(files)} files, {size / 1e6:.1f} MB, {len(index)} replays "
          f"({', '.join(r['symbol'] or r['token'][:6] for r in index)})")
    if not (DIST / "art" / "manifest.json").exists():
        sys.exit("art/manifest.json missing: run tools/build_art.py first")


if __name__ == "__main__":
    main()
