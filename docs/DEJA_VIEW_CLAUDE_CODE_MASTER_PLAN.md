> **Note added 2026-09-14, after the spike.** This is the original master plan, saved verbatim below this note.
> The spike changed several assumptions; `spike_results.md` is authoritative where they differ. The main changes:
> v1 endpoints (1 credit) replace most v1beta1 historical endpoints; T0 on pump.fun is within about a minute of
> deployment; Launch Reflex is measured on first-hour opportunity (`mfe60`), not 24 h outcomes, and is shown as a
> relative percentile; meaningful buyers are the largest buys of $500+ in the first hour, not the earliest 8;
> launches outside pump.fun are unvalidated. The runner code in section 22 is superseded by `spike_runner.py`,
> `launch_data.py`, and `reflex.py`.

# Déjà View — Claude Code Master Handoff

**Date:** 14 September 2026  
**Competition:** Nansen Meridian Buildathon, 14–27 September 2026  
**Project:** Déjà View  
**Tagline:** *We've seen this trade before.*

---

## 0. Instructions to Claude Code

You are taking ownership of this project locally on the user's Mac.

This document is the **single source of truth**. The architecture below has already been debated and reviewed. **Do not redesign it unless real Nansen API data proves an assumption wrong.**

Your job is to:

1. Create a clean standalone repo for Déjà View.
2. Implement and run the technical spike **before any UI/application work**.
3. Use real Nansen responses to correct beta schema assumptions.
4. Record every result in `spike_results.md`.
5. Stop and report clearly if a kill criterion is met.
6. If the spike passes, build the smallest polished end-to-end competition entry.
7. Keep the README current from day one.
8. Never commit secrets or raw Nansen response dumps.

Do not ask the user to make architecture decisions already frozen here. Use engineering judgement for ordinary implementation details.

---

# 1. Product thesis

Déjà View answers:

> **When a new Solana token starts trading, are historically competent early-launch actors entering — and what previous launches showed a similar actor pattern?**

It is not:
- another Smart Money dashboard;
- a generic wallet-PnL ranker;
- an auto-trader;
- a prediction engine claiming “87% chance of moon”;
- a KumoRadar integration during the competition.

The novel primitive is **Launch Reflex**:

> Has this wallet repeatedly entered other token launches unusually early **before this moment**, and what happened after those entries?

Core pipeline:

```text
Live / replay token
    ↓
Find early actors
    ↓
For each wallet: load cached prior launch entries
    ↓
Cold wallet: pull pre-T0 history and enrich
    ↓
Resolve prior token T0s through shared token_t0 cache
    ↓
Launch Reflex + Confidence
    ↓
Current 4-feature event fingerprint
    ↓
Compare with ~50 historical event fingerprints
    ↓
Show nearest winning AND losing analogues
```

---

# 2. Competition constraints

Official campaign:
https://nansen.ai/campaigns/meridian-buildathon

Submission window: **14–27 September 2026**

Requirements:
- Create a Nansen API key.
- Make at least **1,000 API calls**.
- Build a working demo.
- Post a recording on X tagging `@nansen_ai`.
- Submit email, X post and GitHub repo.

Judging:
- **25% Data Integration**
- **25% Creativity & Originality**
- **25% Functionality & Workability**
- **25% Documentation & Submission**

Nansen says creativity beats complexity; live data must load end-to-end; a broken recording does not qualify; another builder should be able to run it in under 10 minutes; and the recording should be understandable without narration.

Therefore **documentation and demo are product work, not last-night chores.**

---

# 3. Frozen architecture

| Decision | Frozen value |
|---|---|
| Chain | Solana only |
| Reflex | Wallet-first: skill at previous launch entries before current T0 |
| T0 | Timestamp where cumulative DEX volume first crosses a tested threshold; initial candidate = $5,000 |
| T0 thresholds to test | $1k / $5k / $10k |
| Launch entry | Wallet's first qualifying buy within 6h of that token's T0 |
| Persistent cache 1 | `token_t0[token]` |
| Persistent cache 2 | `wallet_launch_entries[wallet]` |
| Score cache | **Do not cache Reflex scores by cutoff** |
| Corpus | ~50 mechanically sampled events, used only for analogue matching |
| Matching features | Actor Quality, Entry Speed, Persistence, Concentration |
| Wallet enrichment cap | 2 pages initially, max 3 / 300 transactions |
| Candidate prior tokens | Resolve max 10 per wallet during spike |
| Live actor cap | 8 meaningful early actors |
| Claims | No probability-of-moon claim |
| Historical display | Losing analogues must remain visible |
| UI | Progressive results, not a long spinner |

## Cache enrichment, not scores

Never use `wallet_reflex[wallet, cutoff]`; each event has a different cutoff.

Store:

```text
wallet_launch_entries[wallet] = [
  {
    prior_token,
    prior_token_t0,
    wallet_first_entry,
    entry_delay_seconds,
    outcome_24h,
    outcome_7d
  },
  ...
]
```

plus:
- `max_transaction_timestamp_reached`
- `min_transaction_timestamp_reached`
- calendar lookback covered
- `fetched_at`
- provenance

At any historical cutoff:

```text
eligible_entries = entries where wallet_first_entry < cutoff_time
Reflex = calculate(eligible_entries)
```

This preserves anti-lookahead and makes enrichment reusable.

---

# 4. T0 definition

Do **not** use deployment time or literal first swap as T0.

Initial definition:

> **T0 = timestamp at which cumulative DEX trading volume first exceeds $5,000 after deployment.**

The spike must compare $1k / $5k / $10k.

The same frozen T0 rule must be used:
- for current events;
- for corpus events;
- when deciding whether a wallet's previous entry was early.

Record deployment→T0 gap and threshold sensitivity.

---

# 5. Boundary semantics

Before any entry-delay calculation, establish whether Nansen's query edges are inclusive.

For product logic always use local half-open intervals:

```text
[start, end)
```

Example:

```text
T0 <= trade < T+15m
T+15m <= trade < T+1h
T+1h <= trade < T+6h
```

If adjacent API queries return a boundary trade:
- do **not** subtract a second;
- locally de-duplicate using transaction/signature ID;
- if no stable ID exists, hash the complete row;
- then apply half-open filtering locally.

---

# 6. Launch Reflex

Reflex is **not generic wallet skill**. Only prior qualifying launch entries count.

For a wallet at cutoff:
1. Load wallet history available before cutoff.
2. Find distinct previously traded tokens.
3. Resolve each token's T0.
4. Find wallet's first qualifying buy.
5. Entry later than 6h is not a launch entry.
6. Calculate post-entry outcome.
7. Score early-entry quality + outcomes.
8. Keep sample confidence separate.

Initial relevance:

| Entry delay | Relevance |
|---|---|
| 0–15m | Very high |
| 15–60m | High |
| 1–3h | Medium |
| 3–6h | Low |
| >6h | Not a launch entry |

Do not lock the final formula before seeing real distributions. Shrink tiny samples toward neutral.

Example display:

```text
LAUNCH REFLEX 84 · HIGH CONFIDENCE
18 prior qualifying launches
Median entry +23m
```

---

# 7. Event fingerprint

V1 uses only four dimensions:

1. **Actor Quality** — weighted Launch Reflex of scoreable early actors.
2. **Entry Speed** — how quickly quality actors appeared.
3. **Persistence** — whether early actors kept accumulating.
4. **Concentration** — whether buying is broad or dominated by a few wallets.

No complex ML is required. Start with standardized features + nearest-neighbour distance.

Show **nearest observed analogues**, not a probability.

---

# 8. Historical corpus

Target about **50 mechanically sampled Solana events**.

Do not hand-pick famous winners.

Use a rule such as:
- young/new token event;
- minimum trading activity / liquidity;
- minimum trader count;
- no future-return filter;
- deterministic selection.

Store derived event data:
- token;
- deployment lower bound;
- T0;
- early-actor state;
- four fingerprint dimensions;
- 6h / 24h / 7d outcomes if available;
- fetch timestamp / provenance.

Corpus is for analogue matching only. It does **not** define Reflex.

---

# 9. Anti-lookahead invariant

Every historical Reflex function requires explicit:

```text
cutoff_time
```

No default of `now`.

No trade after the event cutoff may determine what was known at that event.

README wording:

> **Point-in-time trade cutoff:** Déjà View never uses wallet trades that occur after the event being evaluated. Historical enrichment supplied by Nansen may subsequently be restated or corrected.

---

# 10. Technical spike — MUST happen before application work

Budget: roughly **250–500 calls, staged**.

Create `spike_results.md` and continuously record:
- actual outputs;
- field mappings;
- timings;
- credit charges;
- decisions;
- failures;
- changes to assumptions.

## Test 0 — Adapter, auth, real schema, headers

Prove API key works and inspect beta schemas.

Every request logs to:

```text
spike_out/calls.jsonl
```

Log:
- request time;
- endpoint;
- request hash;
- HTTP status;
- wall-clock ms;
- actual credits charged;
- credits remaining;
- per-second/per-minute limits;
- reset;
- request ID;
- **cumulative successful call count across separate runner invocations**;
- 4xx/5xx body.

Rules:
- `spike_out/` gitignored;
- `.env` gitignored;
- key from environment;
- preserve validation errors;
- raw schema dumps remain local.

Probe:
- `token-information` with required `timeframe: "1h"`;
- `historical-dex-trades`;
- `historical-token-ohlcv`.

After Test 0:
- inspect real fields;
- patch `FIELD_MAP`;
- patch header keys;
- patch request shapes;
- only then continue.

## Test B-lite — discover real T0

Run before Test A.

For three real Solana tokens roughly 30–180 days old:
- deployment is only a lower bound;
- query DEX trades in API-side ascending order;
- accumulate estimated USD volume;
- find first point cumulative volume crosses $5k;
- cache to `spike_out/token_t0.json`.

If no T0:
- widen interval;
- inspect data;
- only change threshold with documentation.

## Test A — intraday fidelity + boundary semantics

Anchor on discovered T0.

Query disjoint windows:

```text
T0 → T+15m
T+15m → T+1h
T+1h → T+6h
```

Verify timestamps are inside requested windows. Ignore raw row-count comparisons. Flag 100-row caps.

Check adjacent overlap with stable trade identity.

Pass:
- at least two tokens show meaningful sub-day data within correct bounds.

Fallback:
- if API truly collapses to day resolution, use D0/D1/D3 and document it.

Regardless, product code uses local `[start, end)` intervals.

## Test B — threshold sensitivity / cost

Compute T0 at $1k / $5k / $10k.

Record:
- deployment→T0;
- threshold drift;
- cold calls per T0;
- real credit charge;
- cache behaviour.

If cold resolution repeatedly needs >3 calls, improve search strategy.

Freeze one threshold after seeing the data.

## Test C — wallet identity / history depth

This is the existential test.

For each of 3 events:
- top 8 meaningful early buyers;
- 2 pages pre-T0 history;
- third only if needed;
- max 300 transactions;
- resolve max 10 candidate prior tokens per wallet;
- dedupe T0 lookups globally;
- persist enrichment into `wallet_launch_entries`.

Per wallet record:
- tx count inspected;
- distinct tokens;
- calendar days covered;
- number of qualifying prior launch entries;
- T0 cache hits/misses;
- time.

Important bias:
high-frequency launch wallets may burn through 300 tx quickly, so calendar lookback matters more than count.

Interpretation:
- 3 scoreable specialists among 8 can be useful.
- **Kill** if interesting events repeatedly have zero scoreable actors.
- Move up-market once and retest before abandoning project.

## Test D — does Reflex discriminate?

Build provisional Reflex from Test C.

Use early-entry relevance + 24h outcome. Shrink tiny samples. Keep confidence separate.

Do not use an invented numeric spread threshold.

Manually compare top 3 vs bottom 3 actual histories.

Question:

> Do these look like meaningfully different kinds/qualities of launch trader?

If not, adjust the formula once based on real evidence.

## Test E — outcomes

Test whether historical OHLCV gives:
- T0 / entry price;
- 6h return;
- 24h return;
- 7d return;
- peak/drawdown if cheap.

Test 0's response header should reveal its real credit charge.

If OHLCV fails, try another Nansen historical price/flow endpoint before adding an external provider.

## Test F — latency

Time full scan:

```text
8 early actors
→ history
→ prior token candidates
→ T0 resolution
→ Launch Reflex
```

Measure:
- cold wall-clock;
- warm wall-clock;
- API calls;
- cache hit rate;
- safe concurrency.

Target warm scan <30s if possible.

If cold >2m:
- pre-warm recording cache;
- document first-run latency;
- use progressive UI.

Only consider Nansen Pro if API rate limits, not our code, are the real bottleneck.

---

# 11. Go / No-Go

Write this into `spike_results.md` before UI.

Proceed only if:
1. intraday reconstruction works or fallback remains compelling;
2. useful events surface ~2–3 scoreable specialists often enough;
3. high/low Reflex wallets visibly differ;
4. outcomes can be calculated with Nansen;
5. warm scan is recordable.

If data says no, stop.

---

# 12. Local data schema

## `token_t0`

```text
token_address
chain
deployment_timestamp
t0_timestamp
threshold_usd
calls_to_resolve
source_endpoint
fetched_at
```

## `wallet_launch_entries`

```text
wallet_address
chain
prior_token_address
token_t0
wallet_first_buy
entry_delay_seconds
entry_delay_bucket
outcome_24h
outcome_7d
history_cutoff_used
source_fetch_timestamp
```

Wallet metadata:

```text
max_transaction_timestamp_reached
min_transaction_timestamp_reached
calendar_days_covered
transactions_inspected
last_enriched_at
```

Move to SQLite once JSON becomes cumbersome.

---

# 13. API call accounting

Competition requires **1,000 API calls**, not 1,000 credits.

`calls.jsonl` is authoritative.

Totals must persist across commands/processes.

Before submission create a verification command showing:
- total requests;
- successful requests;
- endpoint breakdown;
- total credits charged;
- first/last timestamps.

Do not spam meaningless calls. Aim for >1,050–1,100 legitimate successful calls for margin.

---

# 14. Redistribution / repo rules

- derived metrics only in public outputs;
- no raw `spike_out/` in Git;
- no key in Git;
- avoid redistributing Smart Money holdings/leaderboards;
- display **Powered by Nansen API**;
- preserve provenance;
- use wallet/DEX data as inputs to our own derived analytics.

---

# 15. Build phase after spike passes

## Screen 1 — Scan

Token input + progressive states:

```text
REWINDING ONCHAIN ACTIVITY…
EARLY ACTORS FOUND
CHECKING PRIOR LAUNCH BEHAVIOUR…
BUILDING EVENT FINGERPRINT…
SEARCHING HISTORY…
```

## Screen 2 — Early actors

Example:

```text
8 meaningful early actors
3 known launch specialists

7x4…KQ
LAUNCH REFLEX 86 · HIGH
Entered +11m
18 prior qualifying launches
```

Show unscoreable wallets honestly.

## Screen 3 — Fingerprint

Only:
- Actor Quality
- Entry Speed
- Persistence
- Concentration

## Screen 4 — Déjà View

```text
WE'VE SEEN THIS BEFORE.
```

Show three nearest historical analogues, why they match, and outcome.

Keep losers:

```text
Historical A  +184% at 24h
Historical B   +73%
Historical C   -68%
```

No fake probability.

---

# 16. Historical Replay + Live demo

Build both.

Historical Replay:
- deterministic historical event;
- evaluate strictly as-of a historical cutoff.

Live scan:
- show a real token hitting Nansen end-to-end for at least a short section of recording.

Design recording to make sense muted.

---

# 17. README structure

Maintain from day one:

1. What is Déjà View?
2. 30-second explanation.
3. Demo.
4. Why Smart Money ≠ Launch Reflex.
5. Pipeline.
6. T0 definition.
7. Reflex methodology.
8. Anti-lookahead.
9. Four-feature fingerprint.
10. Historical sampling.
11. Nansen endpoints.
12. Caching/performance.
13. Limitations.
14. <10-minute setup.
15. Architecture.
16. Attribution/redistribution.
17. Future work.

---

# 18. Explicitly out of scope

Until after submission:
- Ethereum
- Base
- Robinhood Chain
- Hyperliquid
- X sentiment
- Telegram
- KumoRadar integration
- auto-trading
- portfolio management
- LLM commentary
- complex ML
- predictive probability
- elaborate wallet clustering

---

# 19. Schedule

## Sep 14–16 — spike
Repo, README skeleton, Tests 0/B-lite/A/B/C/D/E/F, written Go/No-Go.

## Sep 17–19 — data layer
T0 cache, wallet enrichment, ~50-event corpus, Reflex, outcomes.

## Sep 20 — matching engine
Four features, normalization, nearest analogues, explanations.

## Sep 21 — UI
Progressive scan, actors, fingerprint, analogues.

## Sep 22 — end-to-end freeze
Historical Replay + live scan + >1,000 legitimate calls + clean-clone test.

## Sep 23 — first recording
Watch muted; fix unclear UX.

## Sep 24–25 — docs/reliability

## Sep 26 — submit

## Sep 27 — emergency buffer only

---

# 20. Mac project setup

Create standalone repo:

```bash
mkdir -p ~/dejaview
cd ~/dejaview
git init

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install requests
```

Create `.gitignore` immediately:

```gitignore
.env
.env.*
!.env.example
spike_out/
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/
.DS_Store
Thumbs.db
.vscode/
.idea/
```

The user's shell supplies:

```bash
export NANSEN_API_KEY="..."
```

Never print or commit the full key.

---

# 21. Test-token bootstrap

Before `test0`, select three **real Solana tokens** roughly 30–180 days old with obvious early DEX trading.

Do not leave placeholders.

Use Nansen screener/historical screener or another public source only to identify candidate addresses and approximate deployment lower bounds. The actual T0/early-trade test must use Nansen.

Record why each token was selected.

---

# 22. Final corrected spike runner

Create this file as `spike_runner.py`.

Run in order:

```bash
python spike_runner.py test0
# inspect output; patch real beta schema / FIELD_MAP if required
python spike_runner.py testBlite
python spike_runner.py testA
python spike_runner.py testB
```

After Test B, implement Tests C–F based on the schemas actually observed.

```python
#!/usr/bin/env python3
"""
Deja View - spike runner: Tests 0, B-lite, A, B.

Run in order. Each stage feeds the next:

    export NANSEN_API_KEY=...
    python spike_runner.py test0     # auth + schema discovery, correct FIELD_MAP
    python spike_runner.py testBlite # discover real T0 per token -> token_t0.json
    python spike_runner.py testA     # intraday fidelity, anchored on discovered T0
    python spike_runner.py testB     # T0 threshold sensitivity + cost

Add spike_out/ to .gitignore. Test 0 writes raw Nansen responses and those must
not reach the public repo.
"""

import os
import sys
import json
import time
import hashlib
import datetime as dt
from pathlib import Path

import requests

BASE = "https://api.nansen.ai"
KEY = os.environ.get("NANSEN_API_KEY")
OUT = Path("spike_out")
OUT.mkdir(exist_ok=True)
T0_CACHE = OUT / "token_t0.json"

# Fallback only. Real figures come from response headers.
CREDITS_FALLBACK = {
    "/api/v1beta1/tgm/historical-dex-trades": 5,
    "/api/v1beta1/tgm/historical-who-bought-sold": 5,
    "/api/v1beta1/tgm/historical-token-flow-summary": 5,
    "/api/v1beta1/token-screener/historical": 5,
    "/api/v1beta1/profiler/address/historical-token-balances": 5,
    "/api/v1beta1/profiler/address/historical-transactions": 5,
    "/api/v1beta1/tgm/historical-top-holders": 25,
    "/api/v1beta1/tgm/historical-pnl-leaderboard": 25,
    "/api/v1beta1/tgm/historical-token-quant-scores": 25,
    "/api/v1beta1/smart-money/historical-token-balances": 25,
}

# Header names are best-effort; test0 prints every header it sees so you can
# correct these once against reality.
HEADER_KEYS = {
    "credits_charged": ["x-credits-charged", "x-nansen-credits-charged"],
    "credits_remaining": ["x-credits-remaining", "x-nansen-credits-remaining"],
    "rate_sec_remaining": ["x-ratelimit-remaining-second"],
    "rate_min_remaining": ["x-ratelimit-remaining-minute"],
    "rate_reset": ["x-ratelimit-reset"],
    "request_id": ["x-request-id", "x-nansen-request-id"],
}

# --- CORRECT THESE AFTER TEST 0 ------------------------------------------
FIELD_MAP = {
    "trade_timestamp": "block_timestamp",
    "trade_value_usd": "estimated_value_usd",
    "trade_wallet": "trader_address",
    "trade_side": "action",
}
# -------------------------------------------------------------------------

ASC = [{"field": "block_timestamp", "direction": "ASC"}]


class NansenClient:
    """Single choke point. Beta schema churn and header parsing land here."""

    def __init__(self, key, ledger=OUT / "calls.jsonl"):
        if not key:
            sys.exit("NANSEN_API_KEY not set")
        self.key = key
        self.ledger_path = ledger
        self.successful_calls, self.credits_charged = self._load_ledger_totals()
        self.session = requests.Session()
        self.last_headers = {}

    def _load_ledger_totals(self):
        """Resume cumulative totals across separate runner invocations."""
        if not self.ledger_path.exists():
            return 0, 0
        last = None
        with open(self.ledger_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    continue
        if not last:
            return 0, 0
        return (
            int(last.get("cum_successful_calls") or 0),
            int(last.get("cum_credits_charged") or 0),
        )

    def post(self, path, body, label="", dump_headers=False):
        req_hash = hashlib.sha256(
            (path + json.dumps(body, sort_keys=True)).encode()
        ).hexdigest()[:12]
        t = time.perf_counter()
        status = None
        err = None
        data = None
        meta = {}

        try:
            r = self.session.post(
                BASE + path,
                headers={"apikey": self.key, "Content-Type": "application/json"},
                json=body,
                timeout=60,
            )
            status = r.status_code
            self.last_headers = dict(r.headers)
            if dump_headers:
                print("  headers:", json.dumps(dict(r.headers), indent=2))

            for out_key, candidates in HEADER_KEYS.items():
                for c in candidates:
                    if c in r.headers:
                        meta[out_key] = r.headers[c]
                        break

            if r.ok:
                data = r.json()
                self.successful_calls += 1
                charged = meta.get("credits_charged")
                self.credits_charged += (
                    int(charged) if charged and str(charged).isdigit()
                    else CREDITS_FALLBACK.get(path, 1)
                )
            else:
                # Keep the JSON error body - this is exactly the schema
                # validation detail test0 exists to surface.
                try:
                    err = json.dumps(r.json())[:1500]
                except Exception:
                    err = r.text[:1500]
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:500]

        ms = round((time.perf_counter() - t) * 1000)
        row = {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "label": label,
            "path": path,
            "request_hash": req_hash,
            "status": status,
            "ms": ms,
            "cum_successful_calls": self.successful_calls,
            "cum_credits_charged": self.credits_charged,
            "error": err,
        }
        row.update(meta)
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(row) + "\n")

        if err:
            print(f"  ! {label or path} [{status}]: {err}")
        return data


def utc(s):
    s = str(s).replace("Z", "+00:00")
    d = dt.datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def rows(resp):
    if resp is None:
        return []
    if isinstance(resp, list):
        return resp
    for k in ("data", "result", "results", "items"):
        v = resp.get(k)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for k2 in ("data", "items"):
                if isinstance(v.get(k2), list):
                    return v[k2]
    return []


def trade_identity(row):
    """Stable trade identity for boundary-overlap checks.

    Prefer a transaction/signature field. If the beta schema has none, hash the
    complete row so two trades by the same wallet in the same second are not
    falsely treated as one trade.
    """
    for key in (
        "transaction_hash", "tx_hash", "signature", "transaction_signature",
        "tx_id", "transaction_id", "id",
    ):
        value = row.get(key)
        if value:
            return f"{key}:{value}"
    canonical = json.dumps(row, sort_keys=True, default=str, separators=(",", ":"))
    return "rowhash:" + hashlib.sha256(canonical.encode()).hexdigest()


def dex_page(c, token, start, end, page, label):
    return c.post(
        "/api/v1beta1/tgm/historical-dex-trades",
        {
            "chain": "solana",
            "token_address": token,
            "date_from": start.isoformat(),
            "as_of_date": end.isoformat(),
            "order_by": ASC,
            "pagination": {"page": page, "per_page": 100},
        },
        label,
    )


# --------------------------------------------------------------- Test 0
def test0(c):
    """Auth, headers, schema. Read the dumps before running anything else."""
    print("Test 0 - adapter, headers, schema discovery\n")
    tok = TOKENS[0]
    deploy = utc(tok["deploy"])

    probes = [
        (
            "/api/v1/token-information",
            {"chain": "solana", "token_address": tok["address"], "timeframe": "1h"},
            "token-information",
        ),
        (
            "/api/v1beta1/tgm/historical-dex-trades",
            {
                "chain": "solana",
                "token_address": tok["address"],
                "date_from": deploy.isoformat(),
                "as_of_date": (deploy + dt.timedelta(days=1)).isoformat(),
                "order_by": ASC,
                "pagination": {"page": 1, "per_page": 10},
            },
            "dex-trades",
        ),
        (
            "/api/v1beta1/tgm/historical-token-ohlcv",
            {
                "chain": "solana",
                "token_address": tok["address"],
                "date_from": deploy.isoformat(),
                "as_of_date": (deploy + dt.timedelta(days=7)).isoformat(),
            },
            "ohlcv",
        ),
    ]

    for i, (path, body, label) in enumerate(probes):
        resp = c.post(path, body, label, dump_headers=(i == 0))
        (OUT / f"schema_{label}.json").write_text(json.dumps(resp, indent=2)[:20000])
        r = rows(resp)
        print(f"{label}: {len(r)} rows -> spike_out/schema_{label}.json")
        if r and isinstance(r[0], dict):
            print("  keys:", sorted(r[0].keys()))
        print()

    print("ohlcv is undocumented for pricing - check its credits_charged in "
          "calls.jsonl, that answers Test E for free.")
    print("Correct FIELD_MAP and HEADER_KEYS, then run testBlite.")


# ---------------------------------------------------- Test B-lite (T0)
def test_blite(c):
    """Discover real T0 per token. Must run before Test A."""
    print("Test B-lite - T0 discovery (ASC ordering, $5k threshold)\n")
    ts_key, usd_key = FIELD_MAP["trade_timestamp"], FIELD_MAP["trade_value_usd"]
    cache = json.loads(T0_CACHE.read_text()) if T0_CACHE.exists() else {}

    for tok in TOKENS:
        deploy = utc(tok["deploy"])
        trades, page, calls, cum = [], 1, 0, 0.0
        t0 = None

        while page <= 6 and t0 is None:
            r = rows(dex_page(c, tok["address"], deploy,
                              deploy + dt.timedelta(days=7), page,
                              f"Blite:{tok['name']}:p{page}"))
            calls += 1
            if not r:
                break
            trades += r
            for x in r:
                cum += float(x.get(usd_key) or 0)
                if cum >= 5000:
                    t0 = x.get(ts_key)
                    break
            if len(r) < 100:
                break
            page += 1

        gap = (utc(t0) - deploy) if t0 else None
        print(f"{tok['name']:12} T0={t0}  ({calls} calls, deploy+{gap})")
        if not t0:
            print("  ! no T0 found - widen the window or lower the threshold")
        cache[tok["address"]] = {
            "name": tok["name"],
            "t0": t0,
            "deploy": deploy.isoformat(),
            "calls_to_resolve": calls,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    T0_CACHE.write_text(json.dumps(cache, indent=2))
    print(f"\n-> {T0_CACHE}. Deploy-to-T0 gaps above are exactly why Test A "
          f"must anchor on T0, not deployment.")


# --------------------------------------------------------------- Test A
def test_a(c):
    """Disjoint windows anchored on real T0. Checks bounds, not row counts."""
    print("Test A - intraday fidelity (disjoint windows)\n")
    if not T0_CACHE.exists():
        sys.exit("Run testBlite first - Test A needs discovered T0s.")
    cache = json.loads(T0_CACHE.read_text())
    ts_key = FIELD_MAP["trade_timestamp"]
    verdicts = []

    for tok in TOKENS:
        entry = cache.get(tok["address"], {})
        if not entry.get("t0"):
            print(f"{tok['name']}: no T0, skipping\n")
            continue
        t0 = utc(entry["t0"])

        windows = [
            ("T0->+15m", t0, t0 + dt.timedelta(minutes=15)),
            ("+15m->+1h", t0 + dt.timedelta(minutes=15), t0 + dt.timedelta(hours=1)),
            ("+1h->+6h", t0 + dt.timedelta(hours=1), t0 + dt.timedelta(hours=6)),
        ]

        seen, in_bounds, total = {}, True, 0
        for label, start, end in windows:
            r = rows(dex_page(c, tok["address"], start, end, 1,
                              f"A:{tok['name']}:{label}"))
            stamps = [utc(x[ts_key]) for x in r if x.get(ts_key)]
            bad = [s for s in stamps if s < start or s > end]
            in_bounds &= not bad
            total += len(r)
            seen[label] = {trade_identity(x) for x in r}
            print(f"{tok['name']:12} {label:10} {len(r):4} trades"
                  f"  out-of-bounds={len(bad)}"
                  f"  capped={'YES' if len(r) >= 100 else 'no'}")

        # Boundary inclusivity: do adjacent windows share the edge trade?
        labels = [w[0] for w in windows]
        overlap = len(seen[labels[0]] & seen[labels[1]]) + \
                  len(seen[labels[1]] & seen[labels[2]])
        print(f"  adjacent-window overlap: {overlap} "
              f"({'boundary appears inclusive - use local half-open filtering/de-duplication'
                  if overlap else 'no overlap observed; still use local half-open windows in product'})")
        print(f"  all timestamps in bounds: {in_bounds}\n")
        verdicts.append(in_bounds and total > 0)

    ok = sum(verdicts) >= 2
    print("PASS - intraday works, keep T+15m/1h/6h" if ok else
          "FAIL - windows collapse to daily, fall back to D0/D1/D3")


# --------------------------------------------------------------- Test B
def test_b(c):
    """Threshold sensitivity: does T0 move materially between $1k/$5k/$10k?"""
    print("Test B - T0 threshold sensitivity\n")
    ts_key, usd_key = FIELD_MAP["trade_timestamp"], FIELD_MAP["trade_value_usd"]
    cache = json.loads(T0_CACHE.read_text()) if T0_CACHE.exists() else {}

    for tok in TOKENS:
        deploy = utc(tok["deploy"])
        trades, page, calls, cum = [], 1, 0, 0.0
        while page <= 6:
            r = rows(dex_page(c, tok["address"], deploy,
                              deploy + dt.timedelta(days=7), page,
                              f"B:{tok['name']}:p{page}"))
            calls += 1
            if not r:
                break
            trades += r
            cum = sum(float(x.get(usd_key) or 0) for x in trades)
            if cum > 10_000 or len(r) < 100:
                break
            page += 1

        marks = {}
        for thresh in (1_000, 5_000, 10_000):
            run = 0.0
            marks[thresh] = None
            for x in trades:
                run += float(x.get(usd_key) or 0)
                if run >= thresh:
                    marks[thresh] = x.get(ts_key)
                    break

        print(f"{tok['name']}  ({calls} calls, {len(trades)} trades)")
        base = marks[1_000]
        for k, v in marks.items():
            drift = ""
            if v and base:
                drift = f"  (+{round((utc(v) - utc(base)).total_seconds()/60)}m vs $1k)"
            print(f"  ${k:>6,}: {v}{drift}")
        print()

        if tok["address"] in cache:
            cache[tok["address"]]["thresholds"] = {str(k): v for k, v in marks.items()}

    T0_CACHE.write_text(json.dumps(cache, indent=2))
    print("If drift between $1k and $5k exceeds ~10 minutes, entry delays are "
          "threshold-sensitive - freeze one value and state it in the README.")


# --------------------------------------------------------------- config
# Replace with 3 real Solana tokens launched 30-180 days ago with obvious
# early activity. 'deploy' is a lower bound from token-information.
TOKENS = [
    {"name": "TOKEN_A", "address": "REPLACE_ME", "deploy": "2026-06-01T00:00:00"},
    {"name": "TOKEN_B", "address": "REPLACE_ME", "deploy": "2026-06-15T00:00:00"},
    {"name": "TOKEN_C", "address": "REPLACE_ME", "deploy": "2026-07-01T00:00:00"},
]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test0"
    client = NansenClient(KEY)
    {"test0": test0, "testBlite": test_blite, "testA": test_a, "testB": test_b}[cmd](client)
    print(f"\nsuccessful calls: {client.successful_calls}  "
          f"credits charged: {client.credits_charged}  ledger: {client.ledger_path}")

```

---

# 23. Execution rules

- Test assumptions instead of defending them.
- Beta schema changes belong in the adapter.
- Record changes in `spike_results.md`.
- Never silently replace Nansen with another provider.
- Never weaken kill criteria after seeing bad data without documenting why.
- Prefer simple auditable calculations.
- Block UI until spike passes.
- Never commit `spike_out/`.
- Never expose the API key.
- Keep setup <10 minutes.
- Preserve raw errors locally for debugging.
- Once evidence validates the architecture, **stop ideating and ship**.

---

# 24. Official references

- Meridian Buildathon: https://nansen.ai/campaigns/meridian-buildathon
- API dashboard / key / credits: https://app.nansen.ai/api
- API usage: https://app.nansen.ai/api?tab=usage-analytics
- API docs: https://docs.nansen.ai
- Getting started: https://academy.nansen.ai/articles/0938495-get-started-with-api
- Authentication: https://docs.nansen.ai/getting-started/authentication
- Credits: https://docs.nansen.ai/getting-started/credits

---

# 25. Definition of done

- Nansen drives actual logic.
- Live scan works.
- Historical Replay works.
- Reflex uses only prior qualifying launch entries.
- Point-in-time cutoffs enforced.
- T0 rule identical everywhere.
- Corpus mechanically sampled.
- Winners and losers shown.
- No fake prediction probability.
- Warm scan recordable.
- >1,000 successful API calls documented.
- Clean README.
- New builder runs in <10 minutes.
- Demo understandable muted.
- No secrets/raw restricted dumps in repo.
- Submit by Sep 26; Sep 27 emergency only.

**Build the evidence first. Then build the product.**
