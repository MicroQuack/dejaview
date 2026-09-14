#!/usr/bin/env python3
"""Déjà View local web app.

    .venv/bin/python app.py        # then open http://localhost:8420

Uses only the Python standard library plus requests. One scan runs at a time.
"""

import json
import os
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from nansen_client import NansenClient
from reflex import Scanner

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("DEJAVIEW_PORT", "8420"))
TOKEN_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")  # Solana base58 address

client = NansenClient()
scan_lock = threading.Lock()


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
        if url.path == "/":
            return self.send_text(200, (ROOT / "web" / "index.html").read_text(), "text/html; charset=utf-8")
        if url.path == "/api/scan":
            return self.scan(parse_qs(url.query).get("token", [""])[0].strip())
        return self.send_text(404, "Not found")

    def scan(self, token):
        if not TOKEN_RE.match(token):
            return self.send_text(400, "Enter a Solana token address.")
        if not scan_lock.acquire(blocking=False):
            return self.send_text(409, "A scan is already running. Wait for it to finish.")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def push(kind, data):
                self.wfile.write(f"data: {json.dumps({'kind': kind, **data}, default=str)}\n\n".encode())
                self.wfile.flush()

            try:
                Scanner(client, progress=push).scan(token)
            except (ValueError, RuntimeError) as e:
                push("error", {"message": str(e)})
            except BrokenPipeError:
                pass
            except Exception as e:  # keep the stream readable for the page
                traceback.print_exc()
                push("error", {"message": f"Unexpected error: {type(e).__name__}"})
        finally:
            scan_lock.release()


if __name__ == "__main__":
    print(f"Déjà View running at http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
