# Déjà View spike: review brief

**Date:** 2026-09-14
**Author:** Claude Code
**Reviewer:** Codex
**Status:** spike paused before a retest estimated at about 5,000 credits

## What this brief asks you to do

Review the spike before the user spends more credits. Specifically:

1. Check whether the Test D failure is a real result or an artifact of how we measured it.
2. Check the code for bugs that could change the conclusions.
3. Decide whether the proposed retest is the right next step, or whether a cheaper
   test answers the question first.
4. Flag any place where the work drifted from the master plan without good reason.

Be adversarial. The most useful finding is a flaw that makes the results wrong.

## Context

The master plan is `DEJA_VIEW_CLAUDE_CODE_MASTER_PLAN.md`. The user has it; it is not in
the repo. Ask the user for it if you do not have it. The short version:

- **Product:** for a new Solana token, find the early buyers. Score each buyer's
  **Launch Reflex**, meaning its record of entering earlier launches early, and what
  happened to those tokens afterward. Then match the event to similar past events.
- **T0:** the first time cumulative DEX volume after deployment reaches $5,000.
- **Launch entry:** a wallet's first buy of a token within 6 hours of that token's T0.
- **Anti-lookahead:** every score takes an explicit cutoff. No data after the cutoff counts.
- **Spike first:** Tests 0, B-lite, A, B, C, D, E, F, then a written Go/No-Go before any UI.
- **Go/No-Go criterion 3:** wallets with high and low Reflex must visibly differ.
  This is the criterion that failed.
- **Competition:** Nansen Meridian Buildathon. Submit by 2026-09-26. Needs 1,000+
  successful API calls, a working demo, a recording, and a repo.

## Where things are

| Path | What it is |
|---|---|
| `spike_results.md` | Full log of every test, finding, and plan change. **Read this first.** |
| `nansen_client.py` | API client. Logs every request to `spike_out/calls.jsonl`. Thread-safe. Retries 429, 502, and 503. |
| `launch_data.py` | T0 resolution, price lookup, wallet first buys, launch pre-filter, `launch_reflex`. |
| `spike_runner.py` | Test commands: `test0`, `testLaunch`, `testC`, `testE`. |
| `spike_out/` | Local only, git-ignored. Raw responses, caches, logs. |
| `spike_out/calls.jsonl` | Authoritative request ledger. |
| `spike_out/token_t0.json` | T0 cache, 180+ tokens. |
| `spike_out/wallet_launch_entries.json` | Per-wallet first buys and scored launch entries. |
| `spike_out/price_points.json` | Price cache keyed by token and 10-minute bucket. |
| `spike_out/wallet_history/` | Raw pre-cutoff wallet trades, one file per wallet. |
| `spike_out/testE_run3.log` | Output of the Test D run discussed below. |

Run with `.venv/bin/python spike_runner.py <command>`. The API key is in `.env`.
**Every command except a fully warm `testE` spends credits.** Set `CREDIT_FLOOR` to cap spending.

## Spend so far

| Item | Value |
|---|---|
| Requests | 1,196 total, 1,096 successful |
| Credits charged | 1,104 (from the `x-nansen-credits-used` header) |
| Balance | 22,991 |
| Failed requests | 69 × 503, 13 × 429, 10 × 500, 6 × 504, 2 × 422. Failed requests cost no credits. |

| Endpoint | Successful calls |
|---|---|
| `/api/v1/tgm/dex-trades` | 842 |
| `/api/v1/tgm/token-information` | 220 |
| `/api/v1/profiler/dex-trades` | 31 |
| `/api/v1/token-screener` | 1 |
| `/api/v1beta1/tgm/historical-dex-trades` | 1 |
| `/api/v1beta1/tgm/historical-token-ohlcv` | 1 |

## Results by test

| Test | Result | One-line reason |
|---|---|---|
| 0: auth and schema | Pass | All endpoints work. Real request shapes differ from the plan's runner. |
| B-lite and B: T0 | Pass | T0 at $5k is within 0 to 77 s of deployment on pump.fun. |
| A: intraday windows | Pass on fidelity | Timestamps always in bounds. Busy tokens time out on page 2+. |
| C: early actors have history | Pass | All 8 CATE early buyers are high-frequency launch buyers. |
| E: outcomes from Nansen | Pass | Price lookups work at 1 credit each. |
| D: Reflex separates wallets | **Fail on this sample** | Score spread matches random chance. |
| F: scan speed | Pass | Cold 129 s, warm 4.4 s. |

## Changes from the plan, and why

| Plan assumption | What we did | Evidence |
|---|---|---|
| Use `v1beta1` historical endpoints (5 credits) | Use `v1` endpoints (1 credit) | `tgm/dex-trades` returned the same 100 of 100 transaction hashes as `historical-dex-trades` for the same window. |
| `per_page` 100 | `per_page` 1,000 | Documented maximum. Page 2+ often times out on busy tokens. |
| Large gap from deployment to T0 | T0 is close to deployment | 3 pump.fun tokens: $5k reached 0 s, 63 s, and 77 s after deployment. |
| Sum trade rows for volume | Count each transaction once | Each swap returns a buyer `BUY` row and a pool `SELL` row with the same hash. |
| Use `token_bought_age_days` to flag launch entries | Free pre-filter only | The field is the token's age today, in whole days, not its age at the trade. |
| OHLCV for outcomes | `tgm/dex-trades` prices | Cheaper and precise to the minute. |
| Max 10 prior tokens per wallet | 25 | With 10, wallets had 1 to 8 scoreable entries, too few to compare. |
| Reflex hit = token up at 24 h | Hit = beat the median launch entry at 24 h | Only 4 to 6% of launch entries were up at 24 h, so every wallet scored near zero. This is the one formula change the plan allows. |

## Test D in detail

### Method as implemented

1. **Events:** CATE and JIMOTHY. Both picked from the current top-volume screener, so both survived.
2. **Early actors** (`spike_runner.early_actors`): buys of at least $200 from deployment to
   T0 + 15 min, sorted by first buy, first 8. JIMOTHY had only 2.
3. **Wallet history** (`launch_data.wallet_history`): `profiler/dex-trades` for
   `[T0 − 7 d, T0)` and `[T0 − 14 d, T0 − 7 d)`, page 1 only, 1,000 rows each.
   Trades at or after the cutoff are dropped.
4. **Candidate prior tokens** (`launch_data.first_buys`, `plausible_launch`): the first buy per
   non-base token, kept if today's age puts deployment within about a day of the buy, and
   bought more than 24 h before the cutoff. The 25 most recent per wallet.
5. **T0 per prior token** (`launch_data.resolve_t0`): `token-information` for deployment, then
   `tgm/dex-trades` from deployment for 6 h, or 7 days if needed, until $5k.
   123 of 180 tokens resolved.
6. **Launch entry:** deployment ≤ first buy < T0 + 6 h. Delays before T0 go into the 0–15 min bucket.
7. **Outcome:** price at first buy + 24 h, divided by the wallet's entry price, minus 1.
   The entry price is `trade_value_usd / token_bought_amount` from the wallet's own row.
8. **Score** (`launch_data.launch_reflex`): delay-weighted share of entries that beat the median
   24 h outcome of all entries in the run (−60%), shrunk toward 50 with k = 3.

### Output

Nine wallets had 8 or more scored entries. Scores from the final warm run, which filled 6 more
prices after a gateway outage: 40, 43, 43, 47, 52, 52, 58, 63, 66.
Median 24 h outcome by wallet ranged from −50% to −76%.

**Chance check:** shuffle all entries across the same 9 wallets, keeping each wallet's entry
count, 2,000 times. A spread in scores at least as wide as the real one appeared in 59% of
shuffles. For the spread in median outcome, 30%.

**Manual check:** the top 3 and bottom 3 histories look the same. All buy pump.fun tokens
within seconds of launch for $15 to $750. Nearly all of those tokens fall 50 to 95% within a day.

## Doubts about my own method

These are the places where I think Test D could be wrong. Please weigh each one.

1. **Low statistical power.** With 12 to 23 entries per wallet, one wallet's hit rate has a
   standard error of about 11 points. Only a very large real difference would show up.
   "No evidence of a difference" is not "no difference". The retest may need more entries
   per wallet, not only more wallets.
2. **Wrong outcome horizon for these traders.** These wallets buy within seconds and likely sell
   within minutes. A 24 h token return measures what happened to the token long after they left.
   Price at +15 min or +1 h, or the peak within 1 h, may be the outcome that reflects skill.
3. **Binary hit discards the fat tail.** Only about 2% of entries doubled within 24 h.
   A wallet that catches one 100x among twenty losers scores below average.
   Wallet 9 caught two runners and ranked last.
4. **Entry price noise.** The wallet's own entry price was 0.44 to 3.4 times the market price in
   the same minute. With a median benchmark, that noise flips hits. A market price for the
   entry minute may be better.
5. **In-sample benchmark.** The −60% median comes from the same entries being scored.
6. **Survivorship in excluded tokens.** 57 of 180 prior tokens had no T0. Many likely never
   reached $5k, meaning they died at once. Excluding them removes the worst picks from every wallet.
7. **Delay weights do nothing.** Almost every entry is in the 0–15 min bucket, so the weights
   are effectively constant.
8. **Homogeneous, correlated sample.** The actor rule selects sniper bots only. Wallets 5, 6, 7,
   and 8 bought in the same second and hold the same tokens, so they are likely one operator
   and not independent.
9. **Short history.** A 1,000-row page covers 0.6 to 5.7 days for most of these wallets. The
   entries come from a narrow slice of recent market conditions.
10. **Pre-filter blind spots.** `plausible_launch` relies on today's whole-day age. It may drop
    real launch entries or keep old tokens bought on a new pool.

## Proposed next steps

### Option A: wide retest (about 5,000 credits)

- About 8 launch events, sampled mechanically, including launches that died. Use
  `token-screener/historical` (5 credits) to sample by past date without survivorship.
- Early actors: the top 20 buyers by size from deployment to T0 + 1 h, not the first 8.
  Collapse wallets that buy the same tokens in the same second into one actor.
- Up to 50 prior entries per wallet, from more history windows.
- Rerun the chance check.

### Option B: cheap check first (about 300 to 500 credits)

Reuse the 171 entries already cached. For each entry, add the market price at entry,
+15 min, and +1 h, plus the peak within 1 h. Rescore with those outcomes and a non-binary
score, for example median log return or runner rate. Rerun the chance check. If the new
outcomes separate these 9 wallets, the 24 h horizon was the problem. If they still do not,
Option A becomes the real test.

**My recommendation:** Option B first, then Option A. B tests doubts 2, 3, and 4 at a tenth
of the cost. It is not a substitute for A, which addresses doubts 1, 6, and 8.

## Questions for you

1. Is any doubt above a bug or design flaw that invalidates Test D as run?
2. What outcome should Launch Reflex use for traders who hold for minutes?
3. Should Reflex score each entry as hit or miss, or use a continuous or tail-aware measure?
4. How should the retest sample events and actors, so the result means something for the product?
5. What result from the retest should count as pass, stated before we run it?
   The plan forbids moving the goalposts after seeing data.
6. If Reflex cannot separate wallets, is there a version of Déjà View worth building?
   For example, fingerprint matching on entry speed, persistence, and concentration alone.
7. Did you spot bugs in `launch_data.py` or `spike_runner.py`?
