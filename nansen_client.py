"""Nansen API client with a persistent call ledger.

Every request goes through NansenClient.post, which appends one row to
spike_out/calls.jsonl. The ledger is the authoritative record of API calls
and credits for the competition.
"""

import datetime as dt
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import requests

BASE = "https://api.nansen.ai"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "spike_out"
OUT.mkdir(exist_ok=True)

# Documented credit costs (docs.nansen.ai/getting-started/credits, 2026-09-14).
# Used only when the response carries no credit header.
CREDITS_DOCUMENTED = {
    "/api/v1/token-screener": 1,
    "/api/v1/tgm/token-information": 1,
    "/api/v1/tgm/dex-trades": 1,
    "/api/v1/tgm/token-ohlcv": 1,
    "/api/v1/profiler/dex-trades": 1,
    "/api/v1beta1/tgm/historical-dex-trades": 5,
    "/api/v1beta1/tgm/historical-token-ohlcv": 5,
    "/api/v1beta1/profiler/address/historical-transactions": 5,
}


def load_key():
    """Read NANSEN_API_KEY from the environment, then from the .env file."""
    key = os.environ.get("NANSEN_API_KEY", "").strip()
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("NANSEN_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    if not key:
        sys.exit("NANSEN_API_KEY is not set. Add it to the .env file.")
    return key


def interesting_headers(headers):
    """Keep headers about credits, rate limits, and request IDs."""
    words = ("credit", "ratelimit", "rate-limit", "request-id", "x-nansen")
    return {k: v for k, v in headers.items() if any(w in k.lower() for w in words)}


class NansenClient:
    def __init__(self, ledger=OUT / "calls.jsonl"):
        self.key = load_key()
        self.ledger_path = ledger
        self.successful_calls, self.credits_charged = self._load_totals()
        self.session = requests.Session()
        self.last_headers = {}
        self.lock = threading.Lock()

    def _load_totals(self):
        """Resume cumulative totals across separate runs."""
        calls, credits = 0, 0
        if self.ledger_path.exists():
            for line in self.ledger_path.read_text().splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                calls = int(row.get("cum_successful_calls") or calls)
                credits = int(row.get("cum_credits_charged") or credits)
        return calls, credits

    def post(self, path, body, label=""):
        req_hash = hashlib.sha256(
            (path + json.dumps(body, sort_keys=True)).encode()
        ).hexdigest()[:12]
        started = time.perf_counter()
        status, err, data, hdrs = None, None, None, {}
        charged = None

        for attempt in range(4):
            try:
                r = self.session.post(
                    BASE + path,
                    headers={"apikey": self.key, "Content-Type": "application/json"},
                    json=body,
                    timeout=90,
                )
            except requests.RequestException as e:
                err = f"{type(e).__name__}: {e}"[:500]
                break
            status = r.status_code
            if status in (429, 502, 503) and attempt < 3:
                time.sleep(1.0 + attempt)  # rate limit or gateway blip: back off and retry
                continue
            self.last_headers = dict(r.headers)
            hdrs = interesting_headers(r.headers)
            # Header names confirmed in Test 0 (2026-09-14).
            charged = r.headers.get("x-nansen-credits-used")
            if r.ok:
                data = r.json()
            else:
                try:
                    err = json.dumps(r.json())[:1500]
                except ValueError:
                    err = r.text[:1500]
            break

        with self.lock:
            if data is not None:
                self.successful_calls += 1
                if charged is not None and str(charged).replace(".", "", 1).isdigit():
                    self.credits_charged += float(charged)
                else:
                    self.credits_charged += CREDITS_DOCUMENTED.get(path, 0)
            self._write_row(label, path, req_hash, status, started, charged, hdrs, err)

        if err:
            print(f"  ! {label or path} [{status}]: {err}")
        return data

    def _write_row(self, label, path, req_hash, status, started, charged, hdrs, err):
        row = {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "label": label,
            "path": path,
            "request_hash": req_hash,
            "status": status,
            "ms": round((time.perf_counter() - started) * 1000),
            "credits_header": charged,
            "headers": hdrs,
            "cum_successful_calls": self.successful_calls,
            "cum_credits_charged": self.credits_charged,
            "error": err,
        }
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(row) + "\n")


def utc(value):
    d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def rows(resp):
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict) and isinstance(resp.get("data"), list):
        return resp["data"]
    return []
