#!/usr/bin/env python3
"""Déjà View local web app.

    .venv/bin/python app.py        # then open http://localhost:8420

Uses only the Python standard library plus requests. One live scan runs at a time.

Every finished live scan is saved to spike_out/scans/, and saved scans can be
replayed without API calls. Public mode (DEJAVIEW_PUBLIC=1) replays saved scans
only, from data/replays/, so visitors never spend the owner's Nansen credits.
"""

import datetime as dt
import json
import os
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PUBLIC = os.environ.get("DEJAVIEW_PUBLIC") == "1"
PORT = int(os.environ.get("PORT") or os.environ.get("DEJAVIEW_PORT", "8420"))
TOKEN_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")  # Solana base58 address
STATIC = {"/bg.jpg": "image/jpeg", "/hero.jpg": "image/jpeg"}
ART_RE = re.compile(r"^/art/(?:(?:guests|heads)/g\d{2}\.webp|club-bg\.webp|bouncer\.webp|club-loop\.mp4|bouncer-loop\.webm|manifest\.json)$")
ART_TYPES = {".webp": "image/webp", ".json": "application/json", ".mp4": "video/mp4", ".webm": "video/webm"}
# The demo launch a first-time visitor should meet first. The rest follow, newest first.
FEATURED = ["98kfF7rmsg1QDUEoCqNE7g7M1FdrTt92TEp2CLzypump"]
SAVED = ROOT / "spike_out" / "scans"
REPLAY_DIRS = [ROOT / "data" / "replays"] + ([] if PUBLIC else [SAVED])

scan_lock = threading.Lock()
_client = None


def client():
    global _client
    if _client is None:
        from nansen_client import NansenClient
        _client = NansenClient()
    return _client


def art_type(path):
    """Content type for a built art file (see tools/build_art.py), or None."""
    if not ART_RE.match(path):
        return None
    return ART_TYPES[path[path.rindex("."):]]


def saved_scan(token):
    for d in REPLAY_DIRS:
        path = d / f"{token}.json"
        if path.exists():
            return json.loads(path.read_text())
    return None


def replay_list():
    seen = {}
    for d in REPLAY_DIRS:
        for path in sorted(d.glob("*.json")) if d.exists() else []:
            data = json.loads(path.read_text())
            event = next((e for e in data["events"] if e["kind"] == "event"), None)
            if event and path.stem not in seen:
                seen[path.stem] = {"token": path.stem, "symbol": event.get("symbol"), "t0": event.get("t0"),
                                   "saved_at": data.get("saved_at")}
    order = sorted(seen.values(), key=lambda r: r["t0"] or "", reverse=True)
    return sorted(order, key=lambda r: FEATURED.index(r["token"]) if r["token"] in FEATURED else len(FEATURED))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_text(self, code, body, ctype="text/plain; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/":
            return self.send_text(200, (ROOT / "web" / "index.html").read_text(), "text/html; charset=utf-8")
        if url.path == "/api/scan":
            return self.scan(query.get("token", [""])[0].strip(), query.get("replay", ["0"])[0] == "1")
        if url.path == "/api/replays":
            return self.send_text(200, json.dumps({"public": PUBLIC, "replays": replay_list()}), "application/json")
        ctype = STATIC.get(url.path) or art_type(url.path)
        if ctype and (ROOT / "web" / url.path.lstrip("/")).exists():
            data = (ROOT / "web" / url.path.lstrip("/")).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            return self.wfile.write(data)
        return self.send_text(404, "Not found")

    def open_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def push(self, kind, data):
        try:
            self.wfile.write(f"data: {json.dumps({'kind': kind, **data}, default=str)}\n\n".encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the page closed; let a live scan finish so it can be saved

    def scan(self, token, replay):
        if not TOKEN_RE.match(token):
            return self.send_text(400, "Enter a Solana token address.")
        saved = saved_scan(token)
        if saved and (replay or PUBLIC):
            self.open_stream()
            for e in saved["events"]:
                self.push(e["kind"], {k: v for k, v in e.items() if k != "kind"} | {"replayed": True})
            return
        if PUBLIC:
            self.open_stream()
            return self.push("error", {"message": "This public demo replays saved launches only. Pick one below, "
                                                  "or run Déjà View locally with your own Nansen key to scan any launch."})
        if not scan_lock.acquire(blocking=False):
            return self.send_text(409, "A scan is already running. Wait for it to finish.")
        try:
            from reflex import Scanner
            self.open_stream()
            events = []

            def record(kind, data):
                events.append({"kind": kind, **json.loads(json.dumps(data, default=str))})
                self.push(kind, data)

            try:
                Scanner(client(), progress=record).scan(token)
                SAVED.mkdir(parents=True, exist_ok=True)
                (SAVED / f"{token}.json").write_text(json.dumps(
                    {"saved_at": dt.datetime.now(dt.timezone.utc).isoformat(), "events": events}))
            except (ValueError, RuntimeError) as e:
                self.push("error", {"message": str(e)})
            except Exception as e:  # keep the stream readable for the page
                traceback.print_exc()
                self.push("error", {"message": f"Unexpected error: {type(e).__name__}"})
        finally:
            scan_lock.release()


if __name__ == "__main__":
    host = "0.0.0.0" if PUBLIC else "127.0.0.1"
    print(f"Déjà View running at http://localhost:{PORT}" + (" (public replay mode)" if PUBLIC else ""))
    ThreadingHTTPServer((host, PORT), Handler).serve_forever()
