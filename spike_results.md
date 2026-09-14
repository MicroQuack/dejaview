# Spike results

Running log of what the Nansen API actually does, compared with the plan's
assumptions. Raw responses stay in `spike_out/`, which git ignores.

## Test 0: auth, schema, credit headers (2026-09-14)

**Result: pass.** All six requests returned HTTP 200. Test 0 cost 14 credits.

### Credits and limits

| Finding | Detail |
|---|---|
| Free tier allowance | The response header says the free tier gets 10 credits a day, reset at midnight UTC. |
| Starting balance | 95 credits. 81 remain after Test 0. |
| Credit headers | `x-nansen-credits-cost`, `x-nansen-credits-used`, `x-nansen-credits-remaining` |
| Rate limit headers | `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset`, plus `-second` and `-minute` variants |
| Failed requests | `x-ratelimit-remaining-credit-fails-minute` allows 10 a minute. This suggests failed requests are rate limited separately. Not yet confirmed whether they cost credits. |

### Real credit charges

| Endpoint | Credits | Time |
|---|---|---|
| `/api/v1/token-screener` | 1 | 1.3 s |
| `/api/v1/tgm/token-information` | 1 | 0.5 s |
| `/api/v1/tgm/dex-trades` | 1 | 0.9 s |
| `/api/v1beta1/tgm/historical-dex-trades` | 5 | 2.9 s |
| `/api/v1/profiler/dex-trades` | 1 | 1.5 s |
| `/api/v1beta1/tgm/historical-token-ohlcv` | 5 | 0.6 s |

### Changes to plan assumptions

1. **Use `/api/v1/tgm/dex-trades` (1 credit) instead of the historical version (5 credits).**
   For the launch window of the probe token, both endpoints returned the same 100 trades.
   The transaction hashes overlapped 100 of 100. The cheap endpoint also returns
   `token_address` and `traded_token_address`, which the historical one omits.
2. **Use `/api/v1/profiler/dex-trades` (1 credit) for wallet history.**
   It returns `token_bought_age_days` on every trade. That field may flag launch
   entries directly and cut T0 lookups. Verify in Test C.
3. **`per_page` goes up to 1,000**, not 100. One request can cover a whole launch window.
4. **Request shapes differ from the plan's runner:**
   - `tgm/dex-trades` and `profiler/dex-trades` take `date: {from, to}`.
   - `historical-dex-trades` takes `date_range: {from, to}`, not `date_from`/`as_of_date`.
   - `token-information` lives at `/api/v1/tgm/token-information`, not `/api/v1/token-information`.
   - `historical-token-ohlcv` requires `timeframe` (`5m` to `1w`).
5. **Intraday data exists.** Trades carry second-level timestamps. Hourly OHLCV returned
   142 candles over 7 days, not truncated.
6. **Screener results include tokenized stocks** (for example, SPCX, MU, SNDK, TTWO).
   They are not memecoin launches. Later tests need a filter, such as pump.fun
   addresses ending in `pump`.

### Probe token

`STONK` (`6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx`). Deployed 2026-07-23T19:06:56Z.
Selected mechanically: highest 24h volume among Solana tokens aged 30 to 180 days,
with liquidity of at least $50k and at least 100 traders.

### Open questions

- How far back does the 1-credit wallet history reach? The first early buyer showed
  only 5 trades in the 90 days before launch. It may be a fresh wallet. Test C answers this.
- Is a 1-credit OHLCV endpoint available? The docs page for `tgm/token-ohlcv` returns 404.

### Budget impact

With 1-credit endpoints, one request costs about 1 credit. The competition needs
1,000 successful requests, so it needs roughly 1,000 credits, not 5,000.

## Tests B-lite, B, and A: launch moment and time windows (2026-09-14)

**Result: intraday data works. Busy launches need a different fetch strategy.**
Cost: 20 credits across two runs. 61 credits remain.

### Test tokens

Selected mechanically from the Test 0 screener results, at no extra cost:
pump.fun launches (address ends in `pump`), highest 24h volume first.

| Token | Address | Deployed (UTC) |
|---|---|---|
| CATE | `Ai66LHZG9MCzg1WKdawwqduVAXpNDUuV8M3uyq5ppump` | 2026-07-26 16:24:38 |
| ANSEM | `9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump` | 2026-06-16 21:05:48 |
| JIMOTHY | `Ge87EtsjwRQbHaqQmKRno69RFTwh9bfSsm99XNxTpump` | 2026-07-16 04:37:37 |

Bias: all three still trade heavily today, so they are survivors. The corpus
in the build phase must sample without this bias.

### T0 by threshold (each swap counted once)

| Token | $1k | $5k | $10k |
|---|---|---|---|
| CATE | deploy + 16 s | deploy + 63 s | deploy + 114 s |
| ANSEM | deploy + 0 s | deploy + 0 s | deploy + 3 s |
| JIMOTHY | deploy + 2 s | deploy + 77 s | deploy + 1 h 53 min |

**Decision: freeze T0 at $5,000 (provisional).** From $1k to $5k, T0 moves at most
77 seconds. From $5k to $10k, T0 moves almost two hours on a quieter launch.

**Finding: on pump.fun, T0 is within about a minute of deployment.** The plan
expected a large deploy-to-T0 gap. For these launches the gap is small.

### Findings

1. **Each swap appears as two rows**: the buyer's `BUY` row and the pool's `SELL` row,
   with the same `transaction_hash` and `token_amount`. Summing rows double-counts
   volume. The runner now counts each transaction once. Early-actor detection must
   also drop the pool address. On JIMOTHY one address took the `SELL` side of 265 of
   267 swaps in the first 15 minutes.
2. **API date edges are inclusive at both ends.** A zero-length window returned the
   trades at that exact second. Product code uses local half-open windows and
   de-duplicates on `(transaction_hash, trader_address, action, token_amount)`.
3. **Timestamps are always in bounds.** No trade fell outside its requested window,
   across all three tokens and all windows.
4. **Long and short queries agree.** The first 15 minutes of JIMOTHY returned the same
   527 rows from a 15-minute query and from a 7-day query.
5. **Busy launches time out after page 1.** Page 1 returns within 1 to 20 seconds.
   Page 2 and later often fail with `query_timeout` (HTTP 500) or a Cloudflare 504.
   ANSEM traded about 1,000 swaps in its first 80 seconds. Splitting windows in half
   did not reliably help.
6. **Failed requests cost nothing.** The credit balance did not change on any
   HTTP 500 or 504. The API allows 10 failed requests a minute.

### Next step for Test C

Avoid deep paging. Request only sizeable buys, with `filters.action = BUY` and a
minimum `value_usd`. "Meaningful early actors" means sizeable buyers anyway.
For wallet history, try `token_bought_age_days` on `profiler/dex-trades` as a launch
entry flag. Because T0 is close to deployment on pump.fun, token age at purchase
approximates entry delay. Spot-check a few against real T0 lookups.

## Test C and a first look at Test D: early buyers and their track record (2026-09-14)

**Result: the kill criterion is not met. Early buyers on a busy launch are launch specialists.**
Cost: 31 credits. 30 credits remain. The two failed requests used a wrong filter name
(`value_usd`; the correct name is `estimated_value_usd`) and cost nothing.

### Method

- Early actors: buys of at least $200 from deployment to T0 + 15 min, earliest 8.
- History: one `profiler/dex-trades` request per wallet, 90 days before T0, newest first,
  `per_page` 1,000. Trades at or after T0 are dropped locally.
- Launch candidates: first buy of a token that falls within about a day of its deployment.
- Deployment lookups: `tgm/token-information` for the 19 most shared candidate tokens.
  Deployment stands in for T0, because Test B showed T0 is within about a minute of
  deployment on pump.fun.

### Findings

1. **`token_bought_age_days` is the token's age today, in whole days.** It is not the
   age at the time of the trade. It works only as a rough, free pre-filter.
2. **CATE: all 8 early buyers are high-frequency launch traders.** Each bought 44 to 596
   distinct tokens, and nearly all were bought close to deployment. Of the 19 tokens
   resolved, wallets matched 1 to 18 confirmed launch entries, with a median delay of 0 to 4 min.
3. **JIMOTHY: only 2 buys of at least $200 in the first 15 minutes.** Small launches have
   few meaningful early actors.
4. **1,000 trades cover only days, not months.** Seven of the eight CATE wallets reached the
   1,000-row cap within 0.6 to 5.7 days. The plan warned about this bias. Page 2 is unreliable
   (Test A), so fetch older history with a separate, older date window instead of paging.
5. **Several wallets look like one operator.** Four CATE wallets (5, 6, 7, 8) entered in the same
   second, and three of them had identical confirmed counts. Collapse same-second, same-size entries
   into one actor before counting specialists.
6. **Every prior token needs its own lookup.** The wallets hold 1,748 distinct candidate tokens.
   Keep the plan's cap of 10 prior tokens per wallet, and prefer tokens shared across wallets.
7. **Wallet sell data looks incomplete for outcomes.** Only 17 of 573 older entries for one
   wallet show a sell. Outcomes must come from token prices (Test E), not realized PnL.

### Provisional Reflex from realized PnL (not reliable, see finding 7)

Scored on entries at least 24 hours before the cutoff that show a sell:

| Wallet | Exited entries | Win rate | Realized PnL |
|---|---|---|---|
| JIMOTHY wallet 2 | 11 | 27% | -$564 |
| CATE wallet 3 | 17 | 59% | +$760 |
| CATE wallet 5 | 55 | 47% | +$6,994 |
| CATE wallet 9 | 65 | 38% | +$27,915 |

The numbers differ between wallets, but the samples are small and the sell data is patchy.
Test D is not yet answered.

### Timing

| Request | Median | Max |
|---|---|---|
| Early buyers | 7.5 s | 7.5 s |
| Wallet history | 2.6 s | 7.0 s |
| Token deployment lookup | 1.4 s | 7.1 s |

At these times, a cold scan of 8 wallets with 10 prior tokens each takes about 2 to 4 minutes
without concurrency. The free tier allows 15 requests a second, so parallel requests should
bring it well under a minute. Test F confirms this.

### Go/No-Go so far

| Criterion | Status |
|---|---|
| Intraday reconstruction works | Yes |
| Useful events show 2 to 3 scoreable specialists | Yes on a busy launch. Weak on a small launch. |
| High and low Reflex wallets visibly differ | Not yet answered. Needs price-based outcomes. |
| Outcomes can be calculated with Nansen | Not yet answered. Test E. |
| Warm scan is recordable | Likely. Test F. |

### Next step

Test E and a proper Test D. For each wallet, take up to 10 prior launch tokens from an older
window (7 to 30 days before T0). For each token, get the deployment date and the price at
entry, +24 h, and +7 d from `tgm/dex-trades` (1 credit a request). Estimated cost: 100 to
150 credits for the CATE wallets.

## Tests E, D, and F: price outcomes, Reflex discrimination, scan speed (2026-09-14)

**Result: outcomes and speed pass. Reflex does not yet separate wallets. Test D fails on this sample.**
The user bought credits: balance 24,008 before these runs, 22,991 after.
The ledger shows 1,096 successful calls in total.

### Test E: outcomes from Nansen prices — pass

- Price at a time t: median `estimated_swap_price_usd` of the first trades in `[t, t + 1 h]`
  from `tgm/dex-trades`. If there are none, the last trades in the day before t. If there are
  still none, the price is 0 (dead token).
- Entry price: the wallet's own buy, `trade_value_usd / token_bought_amount`.
- Check: for 10 entries, the wallet entry price was 0.44 to 3.4 times the market price in the
  same minute. Prices move fast in a launch's first seconds, so this is expected noise. The
  largest outcome (+11,668% at 24 h) is a real runner, not a units error.
- Across 171 launch entries, **6% were up 24 hours after entry. The median entry was down 60%.**
  By 7 days most tokens have no trades.
- `historical-token-ohlcv` is not needed. Every price lookup costs 1 credit.

### Test D: does Reflex separate wallets? — fail on this sample

Wallets: the 10 early actors from CATE and JIMOTHY. Up to 25 prior launch entries each,
most recent first, all with a 24-hour outcome known before the event cutoff.

**Formula adjustment (the one allowed by the plan):** the first version scored a hit as
"price up at 24 h". With a base rate of 4 to 6%, every wallet scored near zero. The new
version scores a hit as "beat the median launch entry at 24 h" and shrinks toward 50.
Weights by entry delay are unchanged.

| Wallet | Reflex | Scored entries | Median 24 h outcome |
|---|---|---|---|
| JIMOTHY wallet 2 | 63 | 12 | -54% |
| CATE wallet 10 | 62 | 14 | -50% |
| CATE wallet 3 | 58 | 19 | -58% |
| CATE wallet 8 | 52 | 20 | -60% |
| CATE wallet 6 | 52 | 20 | -62% |
| CATE wallet 4 | 47 | 22 | -70% |
| CATE wallet 5 | 44 | 21 | -64% |
| CATE wallet 7 | 43 | 13 | -76% |
| CATE wallet 9 | 40 | 23 | -69% |

**Chance check:** shuffling all entries randomly across the same 9 wallets gave a score
spread at least this wide 59% of the time. For median outcome, 30% of the time.
The differences in the table are what luck alone produces.

**Manual comparison:** the top 3 and bottom 3 histories look alike. All buy pump.fun tokens
within seconds of launch for $15 to $750, and nearly all of those tokens fall 50 to 95% within a day.
They are the same kind of trader.

**Why the sample may be the problem, not the idea:**
- The actor rule (earliest 8 buys of at least $200) selects sniper bots only.
- Four CATE wallets (5, 6, 7, 8) buy the same tokens in the same seconds. They look like one operator.
- Two events, both survivors, do not represent launches in general.

### Test F: scan speed — pass

| Run | Wall clock | API calls |
|---|---|---|
| Cold: 10 wallets, 25 prior tokens each | 129 s | 564 |
| Warm: same scan, caches filled | 4.4 s | 25 |

The cold time comes from T0 resolution (62 s) and price lookups (65 s), with 8 parallel
requests. Nansen had a 2-second gateway outage (HTTP 503, "failure to get a peer from the
ring-balancer"). The client now retries 429, 502, and 503 responses.

### Go/No-Go

| Criterion | Status |
|---|---|
| Intraday reconstruction works | Yes |
| Useful events show 2 to 3 scoreable specialists | Yes on a busy launch |
| High and low Reflex wallets visibly differ | **No, on this sample** |
| Outcomes can be calculated with Nansen | Yes |
| Warm scan is recordable | Yes, 4.4 s |

**Decision needed.** Criterion 3 fails. Before abandoning, the plan allows one retest with a
wider sample: more launch events, including launches that died, and early buyers beyond the
first 8 snipers. If the score spread still matches chance, Launch Reflex as specified does not work.

## Test D2: short-horizon recheck — pre-registered before running (2026-09-14)

Codex reviewed `docs/REVIEW_FOR_CODEX.md` and agreed: the first Test D measured the wrong
outcome for sniper wallets, used a binary hit that discards runners, and treated likely
same-operator wallets as independent. This section fixes the rules **before** any data is fetched.
Nothing below changes after results arrive.

### Data

- The launch entries already cached in `spike_out/wallet_launch_entries.json`: the same wallets,
  tokens, T0s, and first buys as the final Test D run. No new wallets or tokens.
- Budget: at most 700 credits. The expected cost is 300 to 500.

### Market prices (Nansen `tgm/dex-trades` only)

For each entry with first buy time `b`:

| Quantity | Definition |
|---|---|
| Entry price `P0` | Median `estimated_swap_price_usd` of trades in `[b − 60 s, b + 60 s]` |
| `P15` | Median price of the first trades in `[b + 15 min, b + 20 min]`; if none, the last trades in `[b, b + 15 min]` |
| `P60` | Median price of the first trades in `[b + 60 min, b + 65 min]`; if none, the last trades in `[b, b + 60 min]` |
| `Pmax` | 5th-highest trade price in `[b, b + 60 min]`. The 5th, not the 1st, so one bad print cannot set it. |

The wallet's own computed trade price is **not** used, because it differed from market by 0.44× to 3.4×.
Entries with no `P0` are dropped.

### Metrics (exactly four)

All log returns are capped to `[−ln 10, +ln 10]`, so one 100x cannot dominate.

1. `r15` = ln(`P15` / `P0`)
2. `r60` = ln(`P60` / `P0`)
3. `mfe60` = ln(`Pmax` / `P0`), the best price reachable within the first hour
4. `runner60` = 1 if `Pmax` ≥ 2 × `P0`, else 0

An actor's score on a metric is the mean over its entries. No delay weights: in Test D almost
every entry was in the 0–15 min bucket, so weights did nothing.

### Actors

- Merge wallets into one actor when at least half of the smaller wallet's entries are the same
  token bought within 5 seconds of the other wallet's buy. Merged actors keep one entry per token.
- An actor needs at least 8 entries with `P0` to be included.

### Test

- Statistic: the standard deviation of actor scores.
- Null: shuffle all entries across actors, keeping each actor's entry count, 5,000 times.
- Percentile: the share of shuffles with a smaller standard deviation than the real one.

### Verdict rules

Four metrics are tested, so one metric at 90% happens by luck about a third of the time.

| Verdict | Rule |
|---|---|
| **PASS** | At least one metric at ≥ 95%, or at least two metrics at ≥ 90%. It must also survive both robustness checks, and the top and bottom actors must look different on manual inspection. |
| **PROMISING** | Exactly one metric at ≥ 90% and below 95%, or a PASS that fails a robustness check. |
| **FAIL** | No metric at ≥ 90%. |

Robustness checks, for any metric that qualifies:

1. **Leave one actor out:** the percentile stays at ≥ 80% with each actor removed in turn.
2. **Drop each actor's best entry:** the percentile stays at ≥ 90%.

### What each verdict leads to (agreed with Codex)

- **PASS or PROMISING:** run the wide retest with unbiased events and actor sampling.
- **FAIL:** do not run the 5,000-credit retest as designed. Run one smaller check with a different
  actor rule: meaningful-size, independent, non-pool buyers anywhere in the first hour.
  If that also fails, Launch Reflex is dead, and the fallback is event-pattern matching only.

### Known bias carried into D2

57 of 180 prior tokens have no T0 and are excluded, probably the worst picks. D2 does not fix
this. The wide retest must count "entered a token that never reached $5k" as a failed launch,
not as missing data.

### Test D2 results (run 2026-09-14, after the rules above were frozen)

**Verdict under the frozen rules: PASS.** Manual inspection agrees.
Cost: 587 credits (22,990 to 22,403). This is above the 300–500 estimate and under the 700 cap.
Coverage: 119 of 136 token and buy-time pairs stored; 147 entries had an entry price.
Actors: 10 wallets became 8 actors. Wallets 6, 7, and 8 merged into one. 7 actors had 8+ entries.

| Metric | Percentile vs shuffles | Leave one actor out (min) | Drop best entry | Qualifies |
|---|---|---|---|---|
| `r15` | 99.5% | 97% | 100% | Yes |
| `r60` | 89.8% | not run | not run | No |
| `mfe60` | 98.3% | 90% | 99% | Yes |
| `runner60` | 99.5% | 91% | 100% | Yes |

| Actor | Entries | Mean `r15` | Mean `mfe60` | Runner rate |
|---|---|---|---|---|
| Wallets 6+7+8 | 16 | +0.46 | +1.26 | 62% |
| Wallet 5 | 20 | +0.00 | +1.24 | 70% |
| Wallet 4 | 20 | +0.09 | +1.04 | 60% |
| Wallet 3 | 18 | −0.31 | +0.92 | 50% |
| Wallet 9 | 20 | −0.28 | +0.75 | 45% |
| Wallet 10 | 16 | −0.91 | +0.68 | 25% |
| JIMOTHY wallet 2 | 10 | −0.82 | +0.44 | 10% |

**Manual inspection:** the top two actors often hold tokens that are up 100% to 900% at 15 minutes,
and most of their entries reach 2x within the hour. The bottom two are mostly down 50% to 90% at
15 minutes, and 1 in 4 or fewer reach 2x. They look like different quality of launch picking.

### Checks beyond the frozen rules

- **Not just speed.** Across entries, correlation between entry delay and `mfe60` is −0.15, and
  with `r15` it is −0.03. The two weakest actors (wallet 10, JIMOTHY wallet 2) have median
  delays of 0 s and −8 s, among the fastest.
- **Caveat: shared tokens.** 147 entries cover 105 distinct tokens. Wallet 5 and the 6+7+8 actor
  share about 7 tokens but did not meet the merge rule. The shuffle treats entries as independent,
  so shared tokens make the null too narrow and the percentiles somewhat optimistic.
  The wide retest should shuffle whole tokens, not single entries.
- **Caveat: sample.** Still 2 survivor events and sniper actors only. D2 shows short-horizon Reflex
  can separate these wallets. It does not show the result generalizes.

### Consequences for the product

- **Launch Reflex outcome horizon changes from 24 h to the first hour** (`r15`, `mfe60`, runner rate).
  24 h outcomes stay available for display only.
- Scores use market prices, capped log returns, and merged same-operator actors.
- Next, per the agreed decision tree: the wide retest, with its pass rules frozen first. It must add
  unbiased event sampling, first-hour meaningful buyers, a failed-launch penalty for tokens that
  never reach $5k, and a token-level shuffle.

## Test D3: wide retest — frozen

Rules: `docs/D3_RETEST_PLAN.md` version 2, after Codex review. Frozen at 2026-09-14T14:37:10Z,
file SHA-256 prefix `b06c1c537cd07f0f`, before any D3 request. The rules do not change after data arrives.

**Implementation fix, not a rule change (2026-09-14, first Stage 1 run):** the validation stopped
D3 with "1 of 5". Four of the five checks were request timeouts (HTTP 500 and 504) on T0 lookups
for very busy launches, and the code counted a timeout as a failed check. The one token that
answered was deployed 2026-06-11 07:18 UTC, within a day of the sample date. Fixes:
validation now reads deployment from `token-information` with retries; `resolve_t0` tries a
10-minute window before 6 hours, so busy launches no longer time out; eligibility retries API
failures and logs any candidate skipped for failure. Skipping busy launches silently would have
biased the sample toward quiet launches. Cost of the aborted run: about 12 credits.

### D3 Stages 1–3 results (2026-09-14)

- Stage 1 validation: 5 of 5 tokens deployed within a day of the sample date. The screener is point-in-time.
- Events: 8 of 10 dates. 2026-07-29 and 2026-08-05 had no eligible token in 15 candidates.
  The screener hit the 4-page cap on 6 dates, recorded per event. No candidate was skipped for API failure.
- Stage 3: 84 wallet histories. 30 wallets passed the 20-candidate gate. No wallets merged.
- **Spend gate: PASS at the minimum.** 6 events, 30 actors, 14% shared token pairs.
- D3 spend so far: 651 credits.

**Risk before Stage 4 (no outcome data seen):** the verdict needs 30 actors with 16+ priced
entries. The gate has exactly 30 actors with 20+ candidates. In Test E and D2, about 65–80% of
candidates became launch entries and 86% of entries had `P0`. Many actors are likely to end with
fewer than 16 entries, so Stage 4 as frozen will probably return INCONCLUSIVE after about 3,000 credits.
Paused for a user decision.

**Amendment 1 frozen** at 2026-09-14T15:11:41Z (plan file SHA-256 prefix `7c7ede6c7034b0b0`), after Codex review and user approval:
add extra dates (original + 3 days) until 40 independent actors pass the gate, at most 10 dates.
Same rules and cap. No outcome data had been fetched.

**Amendment 1 result:** 4 extra dates added (2026-06-13, 06-20, 06-27, 07-04). 40 independent actors
from 8 events passed the gate; the stop rule was met. No wallets merged; 18.7% shared token pairs.
3 wallet histories on 2026-06-27 failed and were not retried, because the stop rule was met.
D3 spend before Stage 4: 876 credits. Implementation fix: the budget counter read 0 after an error
response with no credit header; it now keeps the last known balance, so the cap holds.

### D3 results: **PASS** (2026-09-14)

Spend: 5,488 credits of the 6,000 cap (22,403 to 16,915). 37 of 40 actors had 16+ priced entries,
from 8 events. 730 entries in total, including 74 failed launches.
First pass: 30 actors; 10 hit HTTP 429 rate limits after retries and completed on a second pass
from cache. No actor was lost to API failure.

| Test | Result | Rule | Pass |
|---|---|---|---|
| P1 persistence `mfe60` | ρ = 0.424, 99.6% | ρ ≥ 0.25 and ≥ 95% | Yes |
| S2 persistence `r15` | ρ = 0.364, 98.6% | reported | — |
| S3 persistence `runner60` | ρ = 0.521, 100.0% | reported | — |
| S1 spread, unique tokens | 35 actors, 100% | ≥ 95% for the second route | — |
| R1 leave one event out | 96.6% to 100% in 8 of 8 runs | ≥ 90% in 80% of runs | Yes |
| R2 drop best entry | 99.9% | ≥ 90% | Yes |
| R3 unique tokens only | 35 actors, 99.3% | ≥ 80% | Yes |
| K1 newer-half median `mfe60`, top 5 vs bottom 5 | +1.53 vs +0.34 | top above bottom | Yes |
| K2 newer-half runner rate, top 5 vs bottom 5 | 75% vs 22% | top above bottom | Yes |

### Manual inspection for bugs and confounds (not a gate)

- **Market period:** subtracting the average `mfe60` of all entries bought in the same calendar week
  leaves ρ = 0.373 at 99.1%. A hot or cold market week does not explain the result.
- **Entry speed:** actor median entry delay vs mean `mfe60` has rank correlation 0.136. After also removing
  speed-tercile averages, persistence is ρ = 0.357 at 98.7%. Faster buying does not explain the result.
- **Actor mix:** median entry delays range from 0 s to 4,722 s. The D3 actor rule found late,
  sizeable buyers as well as snipers, unlike D2.
- **Absolute level:** every actor's mean `mfe60` is positive, because the 5th-highest price in an hour is
  usually above the entry price. Only the ranking between actors carries information. The product must
  show Reflex relative to other launch buyers, never as an absolute return.
- **Effect size:** moderate. ρ ≈ 0.4 means past Reflex shifts the odds; it does not guarantee. One actor
  in the top third fell from +0.74 to −0.02.

### Go/No-Go: **GO**

| Criterion | Status |
|---|---|
| Intraday reconstruction works | Yes |
| Useful events show scoreable specialists | Yes: 37 of 40 sampled first-hour buyers were scoreable |
| High and low Reflex wallets visibly differ | **Yes, and the difference persists over time (D3)** |
| Outcomes can be calculated with Nansen | Yes |
| Warm scan is recordable | Yes, 4.4 s |

**Frozen product definition from the spike:**

- Launch Reflex = shrunk mean of `mfe60` over a wallet's prior launch entries, shown as a percentile
  against other launch buyers, with runner rate and failed-launch rate beside it.
- Wording: "gets into launches that go on to offer strong first-hour opportunities". Never "makes money",
  and no probabilities.
- T0 at $5,000; launch entry within 6 h of T0, or of deployment for failed launches; market prices;
  capped log returns; point-in-time cutoff at the event's T0.
- Limits to state in the README: pump.fun only, moderate effect size, opportunity rather than profit,
  shallow history for high-frequency wallets.
