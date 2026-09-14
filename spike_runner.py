#!/usr/bin/env python3
"""Deja View spike runner.

    .venv/bin/python spike_runner.py test0

Test 0 costs about 14 credits. It picks candidate tokens, then checks auth,
real response schemas, credit headers, and how far back each endpoint reaches.
Raw responses go to spike_out/, which git ignores.
"""

import datetime as dt
import json
import os
import sys
import time

from nansen_client import OUT, NansenClient, interesting_headers, rows, utc

TOKENS_FILE = OUT / "test_tokens.json"


def save(name, resp):
    (OUT / f"schema_{name}.json").write_text(json.dumps(resp, indent=2, default=str)[:40000])


def show_keys(name, resp):
    r = rows(resp)
    if isinstance(resp, dict) and not r and isinstance(resp.get("data"), dict):
        print(f"  {name}: data keys = {sorted(resp['data'].keys())}")
        return
    print(f"  {name}: {len(r)} rows")
    if r and isinstance(r[0], dict):
        print(f"  keys = {sorted(r[0].keys())}")


def test0(c):
    print("Test 0: auth, schema, credit headers, lookback\n")

    # 1. Pick candidate tokens mechanically: Solana, 30-180 days old, still liquid.
    screen = c.post("/api/v1/token-screener", {
        "chains": ["solana"],
        "timeframe": "24h",
        "pagination": {"page": 1, "per_page": 25},
        "filters": {
            "token_age_days": {"min": 30, "max": 180},
            "liquidity": {"min": 50000},
            "nof_traders": {"min": 100},
        },
        "order_by": [{"field": "volume", "direction": "DESC"}],
    }, "test0:screener")
    save("screener", screen)
    print("Response headers about credits and limits:")
    print(json.dumps(interesting_headers(c.last_headers), indent=2))
    show_keys("screener", screen)
    candidates = rows(screen)
    if not candidates:
        sys.exit("Screener returned nothing. Stopping before spending more credits.")
    for t in candidates:
        print(f"    {t.get('token_symbol')!s:12} age={t.get('token_age_days')} "
              f"vol24h={t.get('volume')} liq={t.get('liquidity')} {t.get('token_address')}")
    TOKENS_FILE.write_text(json.dumps(candidates, indent=2, default=str))

    tok = candidates[0]
    addr = tok["token_address"]
    print(f"\nProbe token: {tok.get('token_symbol')} {addr}\n")

    # 2. Token information: deployment date.
    info = c.post("/api/v1/tgm/token-information",
                  {"chain": "solana", "token_address": addr, "timeframe": "1d"},
                  "test0:token-information")
    save("token_information", info)
    show_keys("token-information", info)
    deploy_raw = ((info or {}).get("data") or {}).get("token_details", {}).get("token_deployment_date") \
        or tok.get("token_deployment_date")
    if not deploy_raw:
        sys.exit("No deployment date found. Stopping.")
    deploy = utc(deploy_raw)
    print(f"  deployment date: {deploy.isoformat()}\n")
    window = {"from": deploy.isoformat(), "to": (deploy + dt.timedelta(days=2)).isoformat()}
    asc = [{"field": "block_timestamp", "direction": "ASC"}]

    # 3. Cheap DEX trades (1 credit). Does it reach back to launch day?
    cheap = c.post("/api/v1/tgm/dex-trades", {
        "chain": "solana", "token_address": addr, "date": window,
        "order_by": asc, "pagination": {"page": 1, "per_page": 100},
    }, "test0:tgm-dex-trades")
    save("tgm_dex_trades", cheap)
    show_keys("tgm/dex-trades (1 credit)", cheap)
    cheap_rows = rows(cheap)
    if cheap_rows:
        print(f"  first={cheap_rows[0].get('block_timestamp')} last={cheap_rows[-1].get('block_timestamp')}")
    print()

    # 4. Historical DEX trades (5 credits). Same window, for comparison.
    hist = c.post("/api/v1beta1/tgm/historical-dex-trades", {
        "chain": "solana", "token_address": addr, "date_range": window,
        "order_by": asc, "pagination": {"page": 1, "per_page": 100},
    }, "test0:historical-dex-trades")
    save("historical_dex_trades", hist)
    show_keys("historical-dex-trades (5 credits)", hist)
    hist_rows = rows(hist)
    if hist_rows:
        print(f"  first={hist_rows[0].get('block_timestamp')} last={hist_rows[-1].get('block_timestamp')}")
    a = {r.get("transaction_hash") for r in cheap_rows}
    b = {r.get("transaction_hash") for r in hist_rows}
    print(f"  overlap with cheap endpoint: {len(a & b)} of {len(b)} tx hashes\n")

    # 5. Wallet history before launch (1 credit). Uses the earliest buyer found.
    buyers = [r for r in (cheap_rows or hist_rows) if r.get("action") == "BUY"]
    if buyers:
        wallet = buyers[0]["trader_address"]
        wal = c.post("/api/v1/profiler/dex-trades", {
            "chain": "solana", "address": wallet,
            "date": {"from": (deploy - dt.timedelta(days=90)).isoformat(), "to": deploy.isoformat()},
            "order_by": [{"field": "block_timestamp", "direction": "DESC"}],
            "pagination": {"page": 1, "per_page": 100},
        }, "test0:profiler-dex-trades")
        save("profiler_dex_trades", wal)
        show_keys("profiler/dex-trades (1 credit)", wal)
        wr = rows(wal)
        if wr:
            print(f"  newest={wr[0].get('block_timestamp')} oldest={wr[-1].get('block_timestamp')}")
        print()
    else:
        print("  no buyers in launch window; skipped wallet probe\n")

    # 6. OHLCV (5 credits). Outcome prices.
    ohlcv = c.post("/api/v1beta1/tgm/historical-token-ohlcv", {
        "chain": "solana", "token_address": addr, "timeframe": "1h",
        "date_from": deploy.isoformat(),
        "as_of_date": (deploy + dt.timedelta(days=7)).isoformat(),
    }, "test0:historical-ohlcv")
    save("historical_ohlcv", ohlcv)
    show_keys("historical-token-ohlcv (5 credits)", ohlcv)
    if isinstance(ohlcv, dict):
        print(f"  truncated={ohlcv.get('truncated')} note={ohlcv.get('truncation_note')}")


T0_CACHE = OUT / "token_t0.json"
THRESHOLDS = (1_000, 5_000, 10_000)
# Stop spending when the balance drops below this. Set CREDIT_FLOOR to override.
CREDIT_FLOOR = int(os.environ.get("CREDIT_FLOOR", "55"))


def pick_launch_tokens(n=3):
    """Pump.fun launches (address ends in 'pump'), highest 24h volume first.

    Uses the screener results saved by Test 0, so it costs no credits. The
    suffix rule drops tokenized stocks and wrapped assets from the screener.
    """
    candidates = json.loads(TOKENS_FILE.read_text())
    launches = [t for t in candidates if t["token_address"].endswith("pump")]
    launches.sort(key=lambda t: -float(t.get("volume") or 0))
    return launches[:n]


def trades(c, addr, start, end, label, page=1, per_page=1000):
    resp = c.post("/api/v1/tgm/dex-trades", {
        "chain": "solana", "token_address": addr,
        "date": {"from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "to": end.strftime("%Y-%m-%dT%H:%M:%SZ")},
        "order_by": [{"field": "block_timestamp", "direction": "ASC"}],
        "pagination": {"page": page, "per_page": per_page},
    }, label)
    left = c.last_headers.get("x-nansen-credits-remaining")
    if resp is not None and left is not None and int(left) < CREDIT_FLOOR:
        sys.exit(f"Stopped: {left} credits left, below the floor of {CREDIT_FLOOR}.")
    last_page = ((resp or {}).get("pagination") or {}).get("is_last_page")
    return resp is not None, rows(resp), last_page


def fetch_window(c, addr, start, end, label, max_pages=3, depth=0):
    """All trades in [start, end]. Pages when full. Splits the window on timeout.

    Returns (rows, complete). Failed requests cost no credits (Test 0 ledger).
    """
    out = []
    for page in range(1, max_pages + 1):
        ok, r, last = trades(c, addr, start, end, f"{label}:p{page}", page=page)
        if not ok:
            if page == 1 and depth < 2:
                mid = start + (end - start) / 2
                a, ca = fetch_window(c, addr, start, mid, label + ":a", max_pages, depth + 1)
                b, cb = fetch_window(c, addr, mid, end, label + ":b", max_pages, depth + 1)
                return a + b, ca and cb
            return out, False
        out += r
        if last or len(r) < 1000:
            return out, True
    return out, False


def dedupe(trade_rows):
    """Drop repeat rows. The API edges are inclusive, so split windows can overlap."""
    seen, out = set(), []
    for r in trade_rows:
        k = (r["transaction_hash"], r["trader_address"], r["action"], r["token_amount"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def tx_volume(trade_rows):
    """USD value per transaction, counted once.

    Each swap appears twice: the buyer's BUY row and the pool's SELL row.
    """
    per_tx = {}
    for r in trade_rows:
        h = r["transaction_hash"]
        v = float(r.get("estimated_value_usd") or 0)
        ts = r["block_timestamp"]
        if h not in per_tx or v > per_tx[h][1]:
            per_tx[h] = (ts, v)
    return sorted(per_tx.values())


def cross_times(trade_rows):
    """Timestamp where cumulative USD volume first reaches each threshold."""
    marks, run = {}, 0.0
    for ts, v in tx_volume(trade_rows):
        run += v
        for th in THRESHOLDS:
            if th not in marks and run >= th:
                marks[th] = ts
    return marks, run


def test_launch(c, only=None):
    """Tests B-lite, B, and A in one pass, using 1-credit trade requests."""
    print("Tests B-lite, B, A: find T0, threshold drift, intraday windows\n")
    cache = json.loads(T0_CACHE.read_text()) if T0_CACHE.exists() else {}
    passes = 0

    for tok in pick_launch_tokens():
        sym, addr = tok["token_symbol"], tok["token_address"]
        if only and sym not in only:
            continue
        deploy = utc(tok["token_deployment_date"])
        print(f"== {sym} {addr}  deployed {deploy.isoformat()}")

        # B-lite and B: widen the window from deployment until $10k is reached.
        found, marks, total = [], {}, 0.0
        for hours in (1, 6, 24):
            found, complete = fetch_window(c, addr, deploy, deploy + dt.timedelta(hours=hours),
                                           f"launch:{sym}:{hours}h", max_pages=2)
            found = dedupe(found)
            marks, total = cross_times(found)
            print(f"  deploy..+{hours}h: {len(found)} rows, complete={complete}, "
                  f"${total:,.0f} volume (each swap counted once)")
            if len(marks) == len(THRESHOLDS) or not complete:
                break
        if not found:
            print("  ! no trades returned\n")
            continue

        base = utc(marks[1_000]) if 1_000 in marks else None
        for th in THRESHOLDS:
            v = marks.get(th)
            drift = f"  (+{(utc(v) - base).total_seconds() / 60:.1f} min vs $1k)" if v and base else ""
            gap = f"  deploy+{utc(v) - deploy}" if v else ""
            print(f"  T0 @ ${th:>6,}: {v}{gap}{drift}")

        if 5_000 not in marks:
            print("  ! $5k not reached; skipping window test\n")
            continue
        t0 = utc(marks[5_000])
        (OUT / f"launch_{sym}.json").write_text(json.dumps(found))
        cache[addr] = {
            "token_address": addr, "chain": "solana", "symbol": sym,
            "deployment_timestamp": deploy.isoformat(),
            "t0_timestamp": t0.isoformat(), "threshold_usd": 5_000,
            "thresholds": {str(k): v for k, v in marks.items()},
            "source_endpoint": "/api/v1/tgm/dex-trades",
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

        # Test A: three windows from T0. Check bounds and edge trades.
        windows = [("T0..15m", t0, t0 + dt.timedelta(minutes=15)),
                   ("15m..1h", t0 + dt.timedelta(minutes=15), t0 + dt.timedelta(hours=1)),
                   ("1h..6h", t0 + dt.timedelta(hours=1), t0 + dt.timedelta(hours=6))]
        ok = True
        for name, start, end in windows:
            r, complete = fetch_window(c, addr, start, end, f"A:{sym}:{name}", max_pages=2)
            r = dedupe(r)
            ts = [utc(x["block_timestamp"]) for x in r]
            out = sum(1 for s in ts if s < start or s > end)
            ok &= out == 0 and complete
            last = ts[-1].isoformat() if ts else None
            print(f"  A {name:8} {len(r):5} rows  txs={len({x['transaction_hash'] for x in r}):5}  "
                  f"out-of-bounds={out}  at-start={ts.count(start)} at-end={ts.count(end)}  "
                  f"complete={complete}  last={last}")
        print(f"  in bounds and complete: {ok}\n")
        passes += ok

    T0_CACHE.write_text(json.dumps(cache, indent=2))
    print("Tokens passing window test:", passes)


BASE_SYMBOLS = {"SOL", "WSOL", "USDC", "USDT", "USD1", "JUP", "JITOSOL", "MSOL"}
DAY = dt.timedelta(days=1)


def guard(c):
    left = c.last_headers.get("x-nansen-credits-remaining")
    if left is not None and int(left) < CREDIT_FLOOR:
        sys.exit(f"Stopped: {left} credits left, below the floor of {CREDIT_FLOOR}.")


def early_actors(c, tok, t0, deploy, n=8, min_usd=200):
    """Sizeable buyers from deployment to T0 + 15 min, earliest first."""
    addr, sym = tok["token_address"], tok["symbol"]
    body = {
        "chain": "solana", "token_address": addr,
        "date": {"from": deploy.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "to": (t0 + dt.timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "filters": {"action": "BUY", "estimated_value_usd": {"min": min_usd}},
        "order_by": [{"field": "block_timestamp", "direction": "ASC"}],
        "pagination": {"page": 1, "per_page": 1000},
    }
    resp = c.post("/api/v1/tgm/dex-trades", body, f"C:{sym}:early-buyers")
    guard(c)
    r = rows(resp)
    (OUT / f"testC_{sym}_early_buyers.json").write_text(json.dumps(resp))
    wallets = {}
    for x in r:
        w = x["trader_address"]
        label = (x.get("trader_address_label") or "").lower()
        if any(k in label for k in ("pool", "pump", "raydium", "meteora", "orca", "program")):
            continue
        e = wallets.setdefault(w, {"wallet": w, "first_buy": x["block_timestamp"], "usd": 0.0,
                                   "buys": 0, "label": x.get("trader_address_label")})
        e["usd"] += float(x.get("estimated_value_usd") or 0)
        e["buys"] += 1
    # A pool or router shows up as a "buyer" on every sell; drop very busy addresses.
    busy = {w for w, e in wallets.items() if e["buys"] > max(50, len(r) * 0.2)}
    ranked = sorted((e for w, e in wallets.items() if w not in busy), key=lambda e: e["first_buy"])
    print(f"  {len(r)} sizeable buy rows, {len(wallets)} wallets, dropped busy={len(busy)}, "
          f"page capped={'YES' if len(r) >= 1000 else 'no'}")
    return ranked[:n]


def wallet_history(c, wallet, cutoff, label, lookback_days=90):
    resp = c.post("/api/v1/profiler/dex-trades", {
        "chain": "solana", "address": wallet,
        "date": {"from": (cutoff - lookback_days * DAY).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "to": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")},
        "order_by": [{"field": "block_timestamp", "direction": "DESC"}],
        "pagination": {"page": 1, "per_page": 1000},
    }, label)
    guard(c)
    r = [x for x in rows(resp) if utc(x["block_timestamp"]) < cutoff]  # strict point-in-time cutoff
    return r, resp is not None, len(rows(resp)) >= 1000


def launch_candidates(history, now):
    """First buy per token that could fall within 6 h of that token's deployment.

    token_bought_age_days is the token's age TODAY in whole days, so the
    deployment date is only known to within a day. Keep the plausible ones.
    """
    first_buy, flows = {}, {}
    for x in history:
        ts = utc(x["block_timestamp"])
        b, s = x.get("token_bought_address"), x.get("token_sold_address")
        v = float(x.get("trade_value_usd") or 0)
        if b and (x.get("token_bought_symbol") or "").upper() not in BASE_SYMBOLS:
            f = flows.setdefault(b, {"bought": 0.0, "sold": 0.0})
            f["bought"] += v
            if b not in first_buy or ts < first_buy[b][0]:
                first_buy[b] = (ts, x.get("token_bought_age_days"), x.get("token_bought_symbol"))
        if s and (x.get("token_sold_symbol") or "").upper() not in BASE_SYMBOLS:
            flows.setdefault(s, {"bought": 0.0, "sold": 0.0})["sold"] += v
    cands = {}
    for tok, (ts, age, sym) in first_buy.items():
        if age is None:
            continue
        latest_deploy = now - int(age) * DAY
        earliest_deploy = latest_deploy - DAY
        # Buy within 6 h after deploy, with one day of slack for rounding.
        if earliest_deploy - DAY <= ts <= latest_deploy + dt.timedelta(hours=6) + DAY:
            cands[tok] = {"token": tok, "symbol": sym, "first_buy": ts.isoformat(), **flows[tok]}
    return cands, len(first_buy)


def reflex(entries, cutoff):
    """Provisional Launch Reflex: delay-weighted win rate, shrunk toward 50."""
    weights = [(15 * 60, 1.0), (3600, 0.8), (3 * 3600, 0.5), (6 * 3600, 0.2)]
    k, num, den, scored = 3.0, 0.0, 0.0, 0
    for e in entries:
        if utc(e["first_buy"]) > cutoff - 7 * DAY:
            continue  # outcome still open at the cutoff
        w = next(wt for lim, wt in weights if e["delay_s"] < lim)
        num += w * (1.0 if e["sold"] > e["bought"] else 0.0)
        den += w
        scored += 1
    return round(100 * (num + k * 0.5) / (den + k)), scored


def test_c(c, symbols=("JIMOTHY", "CATE")):
    print("Test C and D: early actors, prior launch entries, provisional Reflex\n")
    t0s = {v["symbol"]: v for v in json.loads(T0_CACHE.read_text()).values()}
    deploy_cache_file = OUT / "token_deploy.json"
    deploys = json.loads(deploy_cache_file.read_text()) if deploy_cache_file.exists() else {}
    now = dt.datetime.now(dt.timezone.utc)
    all_wallets = []

    for sym in symbols:
        tok = t0s[sym]
        t0, deploy = utc(tok["t0_timestamp"]), utc(tok["deployment_timestamp"])
        print(f"== {sym}  T0={t0.isoformat()}")
        actors = early_actors(c, tok, t0, deploy)
        for a in actors:
            started = time.perf_counter()
            hist, ok, capped = wallet_history(c, a["wallet"], t0, f"C:{sym}:{a['wallet'][:6]}")
            cands, distinct = launch_candidates(hist, now)
            stamps = [utc(x["block_timestamp"]) for x in hist]
            days = round((t0 - min(stamps)).total_seconds() / 86400, 1) if stamps else 0
            a.update(event=sym, cutoff=t0.isoformat(), ok=ok, capped=capped, trades=len(hist),
                     distinct_tokens=distinct, days_covered=days if capped else 90,
                     oldest_trade_days=days, candidates=cands,
                     seconds=round(time.perf_counter() - started, 1))
            print(f"  {a['wallet'][:6]}.. entered +{(utc(a['first_buy']) - t0).total_seconds():>5.0f}s "
                  f"${a['usd']:>8,.0f}  history={len(hist):4} capped={'Y' if capped else 'n'} "
                  f"days={a['days_covered']:>5} tokens={distinct:4} launch-candidates={len(cands):3}")
            all_wallets.append(a)
        print()

    # Resolve deployment dates for candidate tokens, most shared first.
    share = {}
    for a in all_wallets:
        for t in a["candidates"]:
            share[t] = share.get(t, 0) + 1
    order = sorted(share, key=lambda t: -share[t])
    hits = sum(1 for t in order if t in deploys)
    print(f"Candidate prior tokens: {len(order)} distinct, cache hits {hits}")
    for t in order:
        if t in deploys:
            continue
        left = int(c.last_headers.get("x-nansen-credits-remaining") or 0)
        if left <= CREDIT_FLOOR:
            break
        info = c.post("/api/v1/tgm/token-information",
                      {"chain": "solana", "token_address": t, "timeframe": "1d"},
                      f"C:deploy:{t[:6]}")
        d = ((info or {}).get("data") or {}).get("token_details", {}).get("token_deployment_date")
        deploys[t] = {"deployment": d, "fetched_at": now.isoformat()}
    deploy_cache_file.write_text(json.dumps(deploys, indent=2))
    print(f"Resolved {sum(1 for t in order if t in deploys)} of {len(order)}\n")

    print("Per wallet (confirmed = buy within 6 h of deployment; deployment used as T0 proxy)")
    for a in all_wallets:
        entries, unresolved = [], 0
        for t, e in a["candidates"].items():
            d = (deploys.get(t) or {}).get("deployment")
            if not d:
                unresolved += 1
                continue
            delay = (utc(e["first_buy"]) - utc(d)).total_seconds()
            if -120 <= delay < 6 * 3600:
                entries.append({**e, "delay_s": max(delay, 0)})
        score, scored = reflex(entries, utc(a["cutoff"]))
        delays = sorted(e["delay_s"] for e in entries)
        med = f"{delays[len(delays) // 2] / 60:.0f}m" if delays else "-"
        wins = sum(1 for e in entries if e["sold"] > e["bought"])
        a.update(confirmed=len(entries), unresolved=unresolved, reflex=score, scored=scored)
        print(f"  {a['event']:8} {a['wallet'][:6]}.. confirmed={len(entries):3} unresolved={unresolved:3} "
              f"median-delay={med:>5} wins={wins:3} scored={scored:3} REFLEX={score}")
    for a in all_wallets:
        a["candidates"] = list(a["candidates"].values())
    (OUT / "testC_wallets.json").write_text(json.dumps(all_wallets, indent=2, default=str))


def test_e(c, symbols=("CATE", "JIMOTHY"), per_wallet=10, workers=8):
    """Tests E, D, and F: price outcomes, Reflex discrimination, scan timing.

    Run twice. The second run reads the caches and shows the warm scan time.
    """
    from concurrent.futures import ThreadPoolExecutor
    import launch_data as ld

    now = dt.datetime.now(dt.timezone.utc)
    t0_cache = ld.JsonCache(ld.T0_FILE)
    entries_cache = ld.JsonCache(ld.ENTRIES_FILE)
    price_cache = ld.JsonCache(OUT / "price_points.json")
    events = {v["symbol"]: v for v in json.loads(T0_CACHE.read_text()).values()}
    calls_start = c.successful_calls
    timings = {}

    def budget_ok():
        left = c.last_headers.get("x-nansen-credits-remaining")
        return left is None or int(left) > CREDIT_FLOOR

    def timed(name, fn):
        s = time.perf_counter()
        out = fn()
        timings[name] = timings.get(name, 0) + time.perf_counter() - s
        return out

    # Stage 1: early actors per event.
    actors = []
    for sym in symbols:
        ev = events[sym]
        t0, deploy = utc(ev["t0_timestamp"]), utc(ev["deployment_timestamp"])
        tok = {"token_address": ev["token_address"], "symbol": sym}
        found = timed("1 early actors", lambda: early_actors(c, tok, t0, deploy))
        for a in found:
            a.update(event=sym, cutoff=t0)
        actors += found
    print(f"Early actors: {len(actors)}  (calls so far {c.successful_calls - calls_start})")

    # Stage 2: wallet history before each cutoff, two date windows. Cached per wallet.
    def enrich_history(a):
        key = a["wallet"]
        cached = entries_cache.get(key)
        if cached and utc(cached["history_to"]) >= a["cutoff"]:
            return cached
        cut = a["cutoff"]
        hist, days = [], []
        for lo, hi in ((cut - 7 * ld.DAY, cut), (cut - 14 * ld.DAY, cut - 7 * ld.DAY)):
            if not budget_ok():
                return None
            ok, r = ld.wallet_history(c, key, lo, hi, f"E:hist:{key[:6]}")
            if not ok:
                return None
            hist += [x for x in r if utc(x["block_timestamp"]) < cut]
            days.append((lo, len(r) >= 1000))
        (OUT / "wallet_history").mkdir(exist_ok=True)
        (OUT / "wallet_history" / f"{key}.json").write_text(json.dumps(hist))
        stamps = [utc(x["block_timestamp"]) for x in hist]
        rec = {"wallet_address": key, "chain": "solana", "history_to": cut.isoformat(),
               "min_transaction_timestamp_reached": min(stamps).isoformat() if stamps else None,
               "max_transaction_timestamp_reached": max(stamps).isoformat() if stamps else None,
               "transactions_inspected": len(hist),
               "windows_capped": [cap for _, cap in days],
               "first_buys": ld.first_buys(hist), "entries": None,
               "last_enriched_at": now.isoformat()}
        entries_cache.put(key, rec)
        return rec

    with ThreadPoolExecutor(workers) as pool:
        recs = timed("2 wallet history", lambda: list(pool.map(enrich_history, actors)))
    print(f"Histories: {sum(1 for r in recs if r)} of {len(actors)}  "
          f"(calls so far {c.successful_calls - calls_start})")

    # Stage 3: choose up to 10 prior tokens per wallet, then resolve T0s once each.
    share = {}
    for r in recs:
        for t in (r or {}).get("first_buys", {}):
            share[t] = share.get(t, 0) + 1
    picks = {}
    for a, r in zip(actors, recs):
        if not r:
            continue
        cands = [b for b in r["first_buys"].values()
                 if ld.plausible_launch(b, now) and utc(b["wallet_first_buy"]) + ld.DAY < a["cutoff"]]
        cands.sort(key=lambda b: b["wallet_first_buy"], reverse=True)  # most recent first, no shared-token bias
        picks[a["wallet"]] = cands[:per_wallet]
    tokens = sorted({b["prior_token_address"] for bs in picks.values() for b in bs})
    print(f"Prior tokens to resolve: {len(tokens)} distinct from {sum(map(len, picks.values()))} picks")

    def t0_job(t):
        return t, (ld.resolve_t0(c, t, t0_cache) if budget_ok() else None)

    with ThreadPoolExecutor(workers) as pool:
        t0s = dict(timed("3 token T0", lambda: list(pool.map(t0_job, tokens))))
    t0_cache.save()
    print(f"T0 resolved: {sum(1 for v in t0s.values() if v and v.get('t0_timestamp'))} of {len(tokens)}  "
          f"cache hits {t0_cache.hits}  (calls so far {c.successful_calls - calls_start})")

    # Stage 4: launch entries and price outcomes.
    jobs = []
    for a in actors:
        for b in picks.get(a["wallet"], []):
            info = t0s.get(b["prior_token_address"])
            if not info or not info.get("t0_timestamp") or not info.get("deployment_timestamp"):
                continue
            buy, t0 = utc(b["wallet_first_buy"]), utc(info["t0_timestamp"])
            if not (utc(info["deployment_timestamp"]) <= buy < t0 + ld.LAUNCH_WINDOW):
                continue
            delay = (buy - t0).total_seconds()
            jobs.append((a, {**b, "token_t0": t0.isoformat(), "entry_delay_seconds": delay,
                             "entry_delay_bucket": ld.delay_bucket(max(delay, 0))}))

    def price_job(job):
        a, e = job
        tok, buy = e["prior_token_address"], utc(e["wallet_first_buy"])
        out = {}
        for name, t in (("24h", buy + ld.DAY), ("7d", buy + 7 * ld.DAY)):
            key = f"{tok}|{t.replace(second=0, microsecond=0, minute=t.minute // 10 * 10).isoformat()}"
            pt = price_cache.get(key)
            if pt is None and budget_ok():
                pt = ld.price_at(c, tok, t, f"E:price{name}:{tok[:6]}", now)
                if pt is not None:
                    price_cache.put(key, pt)
            out[name] = pt
        ep = e.get("entry_price")
        for name in ("24h", "7d"):
            pt = out[name]
            e[f"outcome_{name}"] = (pt["price"] / ep - 1) if pt and ep else None
            e[f"price_{name}_stale"] = pt.get("stale") if pt else None
        return a, e

    with ThreadPoolExecutor(workers) as pool:
        done = timed("4 prices", lambda: list(pool.map(price_job, jobs)))
    price_cache.save()
    by_wallet = {}
    for a, e in done:
        by_wallet.setdefault(a["wallet"], []).append(e)
    for w, es in by_wallet.items():
        rec = entries_cache.get(w)
        rec["entries"] = es
        entries_cache.put(w, rec)
    entries_cache.save()

    # Stage 5: Reflex at each event cutoff.
    scored = [e for es in by_wallet.values() for e in es if e.get("outcome_24h") is not None]
    prior = sum(1 for e in scored if e["outcome_24h"] > 0) / len(scored) if scored else 0.5
    import statistics
    bench = statistics.median(e["outcome_24h"] for e in scored) if scored else 0.0
    results = []
    for a in actors:
        r = ld.launch_reflex(by_wallet.get(a["wallet"], []), a["cutoff"], bench)
        results.append((a, r))
    total = sum(timings.values())
    print(f"\nPrice-based outcomes: {len(scored)} entries scored, share up at 24h = {prior:.0%}, median 24h outcome = {bench:+.0%}")
    print("Stage timings:", {k: round(v, 1) for k, v in timings.items()}, f"total {total:.1f}s")
    print(f"API calls this run: {c.successful_calls - calls_start}  "
          f"T0 cache hits {t0_cache.hits} misses {t0_cache.misses}  price cache hits {price_cache.hits}\n")

    results.sort(key=lambda x: -x[1]["reflex"])
    for i, (a, r) in enumerate(results, 1):
        med = r["median_outcome_24h"]
        print(f"  {i:2}. {a['event']:8} {a['wallet'][:4]}..  REFLEX {r['reflex']:3} {r['confidence']:6} "
              f"n={r['n']:2}  median 24h outcome={'-' if med is None else f'{med:+.0%}'}  runners(>=2x)={r['runners']}")

    def detail(a):
        for e in sorted(by_wallet.get(a["wallet"], []), key=lambda e: e["wallet_first_buy"]):
            o24, o7 = e.get("outcome_24h"), e.get("outcome_7d")
            print(f"      {str(e['symbol'])[:10]:10} delay={e['entry_delay_seconds']:>7.0f}s "
                  f"buy=${e['buy_usd']:>7,.0f}  24h={'-' if o24 is None else f'{o24:+.0%}':>7}  "
                  f"7d={'-' if o7 is None else f'{o7:+.0%}':>7}")

    print("\nTop 3 histories")
    for a, r in results[:3]:
        print(f"  {a['event']} {a['wallet'][:4]}.. REFLEX {r['reflex']}")
        detail(a)
    print("\nBottom 3 histories")
    for a, r in results[-3:]:
        print(f"  {a['event']} {a['wallet'][:4]}.. REFLEX {r['reflex']}")
        detail(a)


D2_FILE = OUT / "d2_market.json"


def d2_entries():
    """Launch entries scored in the final Test D run, with their actor wallet."""
    import launch_data as ld
    cutoffs = {a["wallet"]: utc(a["cutoff"]) for a in json.loads((OUT / "testC_wallets.json").read_text())}
    cache = json.loads(ld.ENTRIES_FILE.read_text())
    out = []
    for w, rec in cache.items():
        if w not in cutoffs:
            continue
        for e in rec.get("entries") or []:
            if e.get("outcome_24h") is not None and utc(e["wallet_first_buy"]) + ld.DAY < cutoffs[w]:
                out.append({"wallet": w, **e})
    return out


def test_d2_fetch(c, workers=8):
    """Market prices around each entry. Rules frozen in spike_results.md, Test D2."""
    from concurrent.futures import ThreadPoolExecutor
    import statistics
    import launch_data as ld

    store = ld.JsonCache(D2_FILE)
    entries = d2_entries()
    keys = sorted({(e["prior_token_address"], e["wallet_first_buy"]) for e in entries})
    print(f"D2 fetch: {len(entries)} entries, {len(keys)} distinct token and buy-time pairs")
    M = dt.timedelta(minutes=1)
    calls_start = c.successful_calls

    def q(tok, start, end, label, field="block_timestamp", direction="ASC", per_page=100):
        resp = c.post("/api/v1/tgm/dex-trades", {
            "chain": "solana", "token_address": tok,
            "date": {"from": ld.iso(start), "to": ld.iso(end)},
            "order_by": [{"field": field, "direction": direction}],
            "pagination": {"page": 1, "per_page": per_page},
        }, label)
        if resp is None:
            return None
        return [float(x["estimated_swap_price_usd"]) for x in rows(resp) if x.get("estimated_swap_price_usd")]

    def at(tok, b, minutes, label):
        fwd = q(tok, b + minutes * M, b + (minutes + 5) * M, label + ":fwd", per_page=10)
        if fwd is None:
            return None, "error"
        if fwd:
            return statistics.median(fwd), "fwd"
        back = q(tok, b, b + minutes * M, label + ":back", direction="DESC", per_page=10)
        if back is None:
            return None, "error"
        return (statistics.median(back), "back") if back else (None, "none")

    def job(key):
        tok, bs = key
        k = f"{tok}|{bs}"
        if store.get(k) is not None:
            return
        left = c.last_headers.get("x-nansen-credits-remaining")
        if left is not None and int(left) <= CREDIT_FLOOR:
            return
        b = utc(bs)
        p0 = q(tok, b - M, b + M, f"D2:p0:{tok[:6]}")
        if p0 is None:
            return  # request failed; retry on next run
        rec = {"p0": statistics.median(p0) if p0 else None}
        if rec["p0"]:
            rec["p15"], rec["p15_src"] = at(tok, b, 15, f"D2:p15:{tok[:6]}")
            rec["p60"], rec["p60_src"] = at(tok, b, 60, f"D2:p60:{tok[:6]}")
            top = q(tok, b, b + 60 * M, f"D2:max:{tok[:6]}", field="estimated_swap_price_usd",
                    direction="DESC", per_page=5)
            if top is None or "error" in (rec["p15_src"], rec["p60_src"]):
                return
            rec["pmax"] = sorted(top)[0] if top else None  # 5th highest, or lowest of fewer
        store.put(k, rec)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(job, keys))
    store.save()
    have = sum(1 for k in keys if store.get(f"{k[0]}|{k[1]}") is not None)
    print(f"Stored {have} of {len(keys)} pairs. API calls this run: {c.successful_calls - calls_start}")


def test_d2_analyze(seed=20260914, shuffles=5000):
    """Score D2 with the frozen rules. Costs no credits."""
    import math
    import random
    import statistics

    market = json.loads(D2_FILE.read_text())
    cap = math.log(10)

    def lr(a, b):
        if not a or not b:
            return None
        return max(-cap, min(cap, math.log(a / b)))

    rows_ = []
    for e in d2_entries():
        m = market.get(f"{e['prior_token_address']}|{e['wallet_first_buy']}")
        if not m or not m.get("p0"):
            continue
        rows_.append({"wallet": e["wallet"], "token": e["prior_token_address"], "symbol": e["symbol"],
                      "b": utc(e["wallet_first_buy"]),
                      "r15": lr(m.get("p15"), m["p0"]), "r60": lr(m.get("p60"), m["p0"]),
                      "mfe60": lr(m.get("pmax"), m["p0"]),
                      "runner60": None if not m.get("pmax") else float(m["pmax"] >= 2 * m["p0"])})
    metrics = ("r15", "r60", "mfe60", "runner60")

    # Merge same-operator wallets.
    by_w = {}
    for r in rows_:
        by_w.setdefault(r["wallet"], []).append(r)
    parent = {w: w for w in by_w}

    def find(w):
        while parent[w] != w:
            w = parent[w]
        return w

    ws = sorted(by_w)
    for i, a in enumerate(ws):
        for b in ws[i + 1:]:
            ta = {}
            for r in by_w[a]:
                ta.setdefault(r["token"], []).append(r["b"])
            same = sum(1 for r in by_w[b]
                       if any(abs((r["b"] - t).total_seconds()) <= 5 for t in ta.get(r["token"], [])))
            if same >= 0.5 * min(len(by_w[a]), len(by_w[b])):
                parent[find(b)] = find(a)
    actors = {}
    for w, rs in by_w.items():
        actors.setdefault(find(w), {}).setdefault("wallets", set()).add(w)
    for root, a in actors.items():
        per_token = {}
        for w in a["wallets"]:
            for r in by_w[w]:
                if r["token"] not in per_token or r["b"] < per_token[r["token"]]["b"]:
                    per_token[r["token"]] = r
        a["entries"] = list(per_token.values())
    included = {k: a for k, a in actors.items() if len(a["entries"]) >= 8}
    print(f"D2 analysis: {len(rows_)} entries with P0, {len(by_w)} wallets -> {len(actors)} actors, "
          f"{len(included)} with 8+ entries")
    for k, a in included.items():
        print(f"  actor {k[:4]}.. wallets={sorted(w[:4] for w in a['wallets'])} entries={len(a['entries'])}")

    def percentile(groups, metric, rng):
        vals = [[r[metric] for r in g if r[metric] is not None] for g in groups]
        vals = [v for v in vals if v]
        if len(vals) < 3:
            return None, None
        real = statistics.pstdev([statistics.mean(v) for v in vals])
        pool = [x for v in vals for x in v]
        sizes = [len(v) for v in vals]
        below = 0
        for _ in range(shuffles):
            rng.shuffle(pool)
            i, means = 0, []
            for n in sizes:
                means.append(statistics.mean(pool[i:i + n]))
                i += n
            below += statistics.pstdev(means) < real
        return below / shuffles, real

    groups = [a["entries"] for a in included.values()]
    names = [k[:4] for k in included]
    results = {}
    print("\n  metric    percentile  spread   actor means")
    for m in metrics:
        pct, real = percentile(groups, m, random.Random(seed))
        results[m] = pct
        means = [statistics.mean([r[m] for r in g if r[m] is not None]) for g in groups]
        print(f"  {m:9} {pct:10.1%}  {real:7.3f}  " + "  ".join(f"{n}={v:+.2f}" for n, v in zip(names, means)))

    robust = {}
    for m, pct in results.items():
        if pct is None or pct < 0.90:
            continue
        loo = [percentile(groups[:i] + groups[i + 1:], m, random.Random(seed))[0] for i in range(len(groups))]

        def drop_best(g):
            vals = [r for r in g if r[m] is not None]
            best = max(vals, key=lambda r: r[m])
            return [r for r in g if r is not best]

        dropped = percentile([drop_best(g) for g in groups], m, random.Random(seed))[0]
        ok = all(x is not None and x >= 0.80 for x in loo) and dropped is not None and dropped >= 0.90
        robust[m] = ok
        print(f"  robustness {m}: leave-one-out={[round(x, 2) if x is not None else None for x in loo]} "
              f"drop-best={dropped:.2f} -> {'OK' if ok else 'FAILS'}")

    at95 = [m for m, p in results.items() if p is not None and p >= 0.95]
    at90 = [m for m, p in results.items() if p is not None and p >= 0.90]
    if at95 or len(at90) >= 2:
        qualifying = at95 or at90
        verdict = "PASS (pending manual inspection)" if all(robust.get(m) for m in qualifying) else "PROMISING (robustness failed)"
    elif len(at90) == 1:
        verdict = "PROMISING"
    else:
        verdict = "FAIL"
    print(f"\n  VERDICT: {verdict}")

    ranked = sorted(zip(names, groups), key=lambda x: -statistics.mean([r["mfe60"] for r in x[1] if r["mfe60"] is not None]))
    for title, sel in (("Top 2 actors by mfe60", ranked[:2]), ("Bottom 2 actors by mfe60", ranked[-2:])):
        print(f"\n  {title}")
        for n, g in sel:
            print(f"    actor {n}..")
            for r in sorted(g, key=lambda r: r["b"]):
                f = lambda v: "-" if v is None else f"{math.exp(v) - 1:+.0%}"
                print(f"      {str(r['symbol'])[:10]:10} 15m={f(r['r15']):>7} 1h={f(r['r60']):>7} "
                      f"best-1h={f(r['mfe60']):>7} runner={'Y' if r['runner60'] else 'n'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test0"
    client = NansenClient()
    if cmd == "testD2":
        test_d2_fetch(client)
        test_d2_analyze()
    elif cmd == "testE":
        test_e(client, per_wallet=int(os.environ.get("PER_WALLET", "10")))
    elif cmd == "testC":
        test_c(client)
    elif cmd == "testLaunch":
        test_launch(client, only=sys.argv[2].split(",") if len(sys.argv) > 2 else None)
    else:
        {"test0": test0}[cmd](client)
    print(f"\nLedger totals: successful calls={client.successful_calls} "
          f"credits (est.)={client.credits_charged}")
