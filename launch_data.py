"""Launch data layer: T0 resolution, prices, wallet launch entries, Launch Reflex.

Caches live in spike_out/ as JSON and store enrichment, never scores. Reflex is
always computed at an explicit cutoff from cached entries.
"""

import datetime as dt
import json
import statistics
import threading

from nansen_client import OUT, rows, utc

T0_THRESHOLD_USD = 5_000
LAUNCH_WINDOW = dt.timedelta(hours=6)
DAY = dt.timedelta(days=1)
BASE_SYMBOLS = {"SOL", "WSOL", "USDC", "USDT", "USD1", "JUP", "JITOSOL", "MSOL"}

T0_FILE = OUT / "token_t0.json"
ENTRIES_FILE = OUT / "wallet_launch_entries.json"


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class JsonCache:
    def __init__(self, path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {}
        self.lock = threading.Lock()
        self.hits = self.misses = 0

    def get(self, key):
        with self.lock:
            if key in self.data:
                self.hits += 1
                return self.data[key]
            self.misses += 1
            return None

    def put(self, key, value):
        with self.lock:
            self.data[key] = value

    def save(self):
        with self.lock:
            self.path.write_text(json.dumps(self.data, indent=2, default=str))


def dex_trades(c, token, start, end, label, direction="ASC", per_page=1000, filters=None):
    body = {
        "chain": "solana", "token_address": token,
        "date": {"from": iso(start), "to": iso(end)},
        "order_by": [{"field": "block_timestamp", "direction": direction}],
        "pagination": {"page": 1, "per_page": per_page},
    }
    if filters:
        body["filters"] = filters
    resp = c.post("/api/v1/tgm/dex-trades", body, label)
    return resp is not None, rows(resp)


def tx_volume(trade_rows):
    """(timestamp, usd) per transaction. Each swap appears as a BUY and a pool SELL row."""
    per_tx = {}
    for r in trade_rows:
        v = float(r.get("estimated_value_usd") or 0)
        h = r["transaction_hash"]
        if h not in per_tx or v > per_tx[h][1]:
            per_tx[h] = (r["block_timestamp"], v)
    return sorted(per_tx.values())


def resolve_t0(c, token, t0_cache):
    """T0 = first time cumulative DEX volume after deployment reaches $5,000."""
    cached = t0_cache.get(token)
    if cached is not None:
        return cached
    calls = 0
    info = c.post("/api/v1/tgm/token-information",
                  {"chain": "solana", "token_address": token, "timeframe": "1d"},
                  f"t0:info:{token[:6]}")
    calls += 1
    data = (info or {}).get("data") or {}
    deploy = (data.get("token_details") or {}).get("token_deployment_date")
    entry = {"token_address": token, "chain": "solana", "symbol": data.get("symbol"),
             "deployment_timestamp": deploy, "t0_timestamp": None,
             "threshold_usd": T0_THRESHOLD_USD, "source_endpoint": "/api/v1/tgm/dex-trades",
             "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    if info is None:
        return None  # request failed; do not cache
    if deploy:
        d = utc(deploy)
        # Short window first: busy launches reach $5k in minutes, and a 6 h query on
        # them times out. The T0 definition is unchanged.
        for span in (dt.timedelta(minutes=10), LAUNCH_WINDOW, 7 * DAY):
            ok, r = dex_trades(c, token, d, d + span, f"t0:trades:{token[:6]}")
            calls += 1
            if not ok:
                return None
            run = 0.0
            for ts, v in tx_volume(r):
                run += v
                if run >= T0_THRESHOLD_USD:
                    entry["t0_timestamp"] = utc(ts).isoformat()
                    break
            if entry["t0_timestamp"]:
                break
            if len(r) >= 1000:
                entry["t0_unresolved_capped"] = True  # 1,000 trades without $5k: unknown, not failed
                break
    entry["calls_to_resolve"] = calls
    t0_cache.put(token, entry)
    return entry


def price_at(c, token, t, label, now):
    """Token price near time t: first trades in [t, t + 1 h], else last trade in the day before."""
    if t > now:
        return None
    ok, r = dex_trades(c, token, t, t + dt.timedelta(hours=1), label + ":fwd", per_page=20)
    stale = False
    if ok and not r:
        ok, r = dex_trades(c, token, t - DAY, t, label + ":back", direction="DESC", per_page=20)
        stale = True
    prices = [float(x["estimated_swap_price_usd"]) for x in r if x.get("estimated_swap_price_usd")]
    if not ok:
        return None
    if not prices:
        return {"price": 0.0, "stale": True, "note": "no trades in the prior day"}
    return {"price": statistics.median(prices[:10]), "stale": stale,
            "at": r[0]["block_timestamp"]}


def wallet_history(c, wallet, start, end, label):
    resp = c.post("/api/v1/profiler/dex-trades", {
        "chain": "solana", "address": wallet,
        "date": {"from": iso(start), "to": iso(end)},
        "order_by": [{"field": "block_timestamp", "direction": "DESC"}],
        "pagination": {"page": 1, "per_page": 1000},
    }, label)
    return resp is not None, rows(resp)


def first_buys(history):
    """Earliest buy per non-base token: time, USD value, and implied price."""
    out = {}
    for x in history:
        tok = x.get("token_bought_address")
        if not tok or (x.get("token_bought_symbol") or "").upper() in BASE_SYMBOLS:
            continue
        ts = utc(x["block_timestamp"])
        if tok in out and utc(out[tok]["wallet_first_buy"]) <= ts:
            continue
        amount = float(x.get("token_bought_amount") or 0)
        value = float(x.get("trade_value_usd") or 0)
        out[tok] = {"prior_token_address": tok, "symbol": x.get("token_bought_symbol"),
                    "wallet_first_buy": ts.isoformat(), "buy_usd": value,
                    "entry_price": value / amount if amount else None,
                    "age_days_today": x.get("token_bought_age_days")}
    return out


def plausible_launch(buy, as_of):
    """Free pre-filter: the token's whole-day age puts deployment within about a day of the buy.

    `as_of` must be when the trade row was fetched, not today. The age travels with the cached row,
    so using the current clock would quietly move the window and change old results.
    """
    age = buy.get("age_days_today")
    if age is None:
        return False
    latest = as_of - int(age) * DAY
    ts = utc(buy["wallet_first_buy"])
    return latest - 2 * DAY <= ts <= latest + LAUNCH_WINDOW + DAY


def delay_bucket(seconds):
    if seconds < 15 * 60:
        return "0-15m"
    if seconds < 3600:
        return "15-60m"
    if seconds < 3 * 3600:
        return "1-3h"
    return "3-6h"


RELEVANCE = {"0-15m": 1.0, "15-60m": 0.8, "1-3h": 0.5, "3-6h": 0.2}


def launch_reflex(entries, cutoff, benchmark_24h, k=3.0):
    """Provisional Launch Reflex at an explicit cutoff.

    Counts only launch entries whose 24 h outcome was known before the cutoff.
    Hit = the token's 24 h outcome after the wallet's entry beat benchmark_24h,
    the median 24 h outcome of launch entries in general. Only about 4% of
    launch entries are up after 24 h, so "up" alone cannot separate wallets.
    The score shrinks toward 50, which means "typical launch buyer".
    """
    if cutoff is None:
        raise ValueError("cutoff is required")
    eligible = [e for e in entries
                if e.get("outcome_24h") is not None
                and utc(e["wallet_first_buy"]) + DAY < cutoff]
    num = sum(RELEVANCE[e["entry_delay_bucket"]] * (e["outcome_24h"] > benchmark_24h) for e in eligible)
    den = sum(RELEVANCE[e["entry_delay_bucket"]] for e in eligible)
    score = round(100 * (num + k * 0.5) / (den + k))
    n = len(eligible)
    confidence = "HIGH" if n >= 8 else "MEDIUM" if n >= 4 else "LOW" if n else "NONE"
    delays = sorted(e["entry_delay_seconds"] for e in eligible)
    outcomes = [e["outcome_24h"] for e in eligible]
    return {"reflex": score, "confidence": confidence, "n": n,
            "median_delay_s": delays[len(delays) // 2] if delays else None,
            "median_outcome_24h": statistics.median(outcomes) if outcomes else None,
            "runners": sum(1 for o in outcomes if o >= 1.0)}


MINUTE = dt.timedelta(minutes=1)


def _prices(c, token, start, end, label, field="block_timestamp", direction="ASC", per_page=100):
    resp = c.post("/api/v1/tgm/dex-trades", {
        "chain": "solana", "token_address": token,
        "date": {"from": iso(start), "to": iso(end)},
        "order_by": [{"field": field, "direction": direction}],
        "pagination": {"page": 1, "per_page": per_page},
    }, label)
    if resp is None:
        return None
    return [float(x["estimated_swap_price_usd"]) for x in rows(resp) if x.get("estimated_swap_price_usd")]


def market_points(c, token, b, label, with_p15=True):
    """P0, P15, and Pmax around a first buy at b (rules from Test D2).

    Returns None when a request fails, so the caller can retry later.
    """
    p0 = _prices(c, token, b - MINUTE, b + MINUTE, f"{label}:p0")
    if p0 is None:
        return None
    rec = {"p0": statistics.median(p0) if p0 else None, "p15": None, "pmax": None}
    if not rec["p0"]:
        return rec
    if not with_p15:
        top = _prices(c, token, b, b + 60 * MINUTE, f"{label}:max", field="estimated_swap_price_usd",
                      direction="DESC", per_page=5)
        if top is None:
            return None
        rec["pmax"] = min(top) if top else None
        return rec
    fwd = _prices(c, token, b + 15 * MINUTE, b + 20 * MINUTE, f"{label}:p15fwd", per_page=10)
    if fwd is None:
        return None
    if fwd:
        rec["p15"] = statistics.median(fwd)
    else:
        back = _prices(c, token, b, b + 15 * MINUTE, f"{label}:p15back", direction="DESC", per_page=10)
        if back is None:
            return None
        rec["p15"] = statistics.median(back) if back else None
    top = _prices(c, token, b, b + 60 * MINUTE, f"{label}:max", field="estimated_swap_price_usd",
                  direction="DESC", per_page=5)
    if top is None:
        return None
    rec["pmax"] = min(top) if top else None  # 5th highest, or the lowest of fewer
    return rec
