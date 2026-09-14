# Test D3: wide retest of Launch Reflex — frozen rules

**Version:** 2, frozen 2026-09-14 before any D3 data was fetched
**Author:** Claude Code. **Reviewed by:** Codex. **Approved by:** the user.

## Changes from version 1 after Codex review

| # | Change | Reason |
|---|---|---|
| 1 | Event sampling drops the day-one $50k volume and 100-trader floor. Eligibility uses only data from the first hours. | The floor used information the product would not have at decision time: survivorship. |
| 2 | Actors need at least 16 entries, and each selects its 20 most recent. The wallet gate needs 20 candidates. | 7 entries per half was too noisy. Fewer, richer actors are better. |
| 3 | Same-operator merge happens in Stage 3, before any price spend and before testing. | A merged cluster counts as one actor. |
| 4 | Stage 3 ends with a spend gate. Stage 4 prices run only if the sample is large and independent enough. | Stage 4 is the expensive part. |
| 5 | PASS rules follow Codex: 80% of leave-one-event-out runs, a unique-token persistence check, and objective sanity checks instead of manual judgement. | Version 1 required every check to pass and used human judgement as a gate. |
| 6 | The claim is opportunity recognition, not trading profit. | `mfe60` does not show whether the wallet sold near the peak. |

## The question D3 answers

> Does a wallet's first-hour launch opportunity on older launches predict its first-hour launch
> opportunity on newer launches, across randomly sampled launches and meaningful first-hour buyers?

A PASS supports this product claim: **this wallet repeatedly gets into launches that go on to offer
unusually strong first-hour opportunities.** It does not show that the wallet makes money.

## Carried over from D2 unchanged

- Market prices from `tgm/dex-trades`, not the wallet's own trade price.
- `P0` = median price in `[b − 60 s, b + 60 s]` around the wallet's first buy `b`.
- `P15` = median of the first trades in `[b + 15 min, b + 20 min]`; if none, the last trades in `[b, b + 15 min]`.
- `Pmax` = 5th-highest trade price in `[b, b + 60 min]`.
- Log returns capped to `[−ln 10, +ln 10]`.
- T0 = first time cumulative volume after deployment reaches $5,000, one count per transaction.
- Point-in-time: the cutoff is the event's T0.

## Stage 1: sample events

**Source:** `/api/v1beta1/token-screener/historical`.

**Sample dates:** 2026-06-10, 06-17, 06-24, 07-01, 07-08, 07-15, 07-22, 07-29, 08-05, 08-12.

**Request per date:**

```json
{
  "chains": ["solana"],
  "to_date": "<date + 1 day>",
  "timeframe_days": 1,
  "apply_blacklist_filter": false,
  "filters": {"token_age_days": {"max": 1}, "volume_usd": {"min": 5000}},
  "order_by": [{"field": "token_age_days", "direction": "ASC"}],
  "pagination": {"page": 1, "per_page": 1000}
}
```

- The only activity floor is $5,000 of day volume. Every event must reach T0 at $5,000 anyway,
  so this floor adds no information the product lacks.
- Ordering by `token_age_days` is unrelated to performance. Fetch pages until `is_last_page`,
  at most 4 pages a date. If a date is capped, record it.

**Candidate order:** pump.fun addresses (ending in `pump`), sorted by `sha256(token_address + date)`.

**Validation, before other spend:** on the first date, check the first 5 candidates in hash order.
At least 4 must have a deployment date within one day of the sample date. If not, stop D3.

**Eligibility, checked in candidate order, at most 15 candidates a date.** The first that passes is the event:

1. Deployment (from `tgm/token-information`) is on the sample date, UTC.
2. T0 is within 6 hours of deployment.
3. At least 6 wallets pass the Stage 2 actor rule.

A date with no eligible candidate yields no event.

## Stage 2: select actors

**Buys:** `tgm/dex-trades` with `{"action": "BUY", "estimated_value_usd": {"min": 500}}`, ordered by
`estimated_value_usd` descending, `per_page` 1,000, in four windows:
`[deploy, T0 + 5 min]`, `[T0 + 5 min, T0 + 15 min]`, `[T0 + 15 min, T0 + 30 min]`, `[T0 + 30 min, T0 + 60 min]`.

**Exclude:**

- Labels containing `pool`, `router`, `program`, `exchange`, `jupiter`, `raydium`, `meteora`,
  `pump`, `binance`, `coinbase`, `okx`, or `bybit`, case-insensitive.
- Addresses with more than 25 qualifying buys in the hour.
- Wallets already used in an earlier event.

**Rank:** total first-hour buy USD, descending. Keep the top 12.

## Stage 3: history, merge, and spend gate

**History:** `profiler/dex-trades`, page 1, 1,000 rows, for `[T0 − 7 d, T0)`, `[T0 − 14 d, T0 − 7 d)`,
and `[T0 − 30 d, T0 − 14 d)`.

**Candidates:** first buy per non-base token that passes `launch_data.plausible_launch`, with
first buy + 6 h before T0. Because deployment is at or before the buy, this also puts deployment + 6 h
and first buy + 1 h before T0.

**Wallet gate:** fewer than 20 candidates, and the wallet stops here.

**Merge:** join two wallets when at least half of the smaller wallet's candidates are the same token
bought within 5 seconds of the other wallet's buy. A merged actor keeps one candidate per token, the earliest.

**Spend gate. Stage 4 runs only if all of these hold:**

1. At least 6 events have an actor that passed the wallet gate.
2. At least 30 independent actors passed the wallet gate.
3. At most 50% of (actor, token) candidate pairs involve a token that another actor also holds.

If the gate fails, the verdict is INCONCLUSIVE, and D3 stops.

## Stage 4: launch entries and outcomes

For each actor, in `sha256(actor)` order:

1. Take its 26 most recent candidates. Resolve deployment and T0 for each (`launch_data.resolve_t0`).
2. **Launch entry:** if T0 is within 6 h of deployment, deployment ≤ buy < T0 + 6 h.
   Otherwise the token is a **failed launch**, and the rule is deployment ≤ buy < deployment + 6 h.
   Failed launches stay in and are scored with the same metrics.
3. Keep the 20 most recent launch entries. Fetch `P0`, `P15`, and `Pmax`. Drop entries without `P0`.

| Metric | Definition | Role |
|---|---|---|
| `mfe60` | ln(`Pmax` / `P0`), capped | **Primary** |
| `r15` | ln(`P15` / `P0`), capped | Secondary |
| `runner60` | 1 if `Pmax` ≥ 2 × `P0` | Secondary |
| `failed_launch` | 1 if failed launch | Reported only |

**Actor inclusion:** at least 16 entries with `P0`.

## Stage 5: tests

All shuffles: 5,000, seed 20260914.

**P1, primary: persistence of `mfe60`.** Sort each actor's entries by time and split into older and
newer halves; the middle entry of an odd count goes to the older half. Statistic: Spearman
correlation across actors between the halves' mean `mfe60`. Null: shuffle newer-half means across
actors. Percentile: share of shuffles with a lower correlation.

**S1: spread on unique tokens.** Standard deviation of actor mean `mfe60`, using only tokens held by
exactly one actor, for actors with at least 8 such entries. Null: shuffle those entries across actors.

**S2 and S3:** P1 for `r15` and `runner60`. Reported only.

**Robustness for P1:**

- **R1, leave one event out:** percentile at least 90% in at least 80% of runs.
- **R2, drop each actor's best entry:** percentile at least 90%.
- **R3, unique tokens only:** P1 using only unique-token entries, for actors with at least 8 of them.
  Percentile at least 80%. If fewer than 15 actors qualify, R3 is not evaluable and does not block.

**Sanity checks:** rank actors by older-half mean `mfe60`. Among the top 5 and bottom 5:

- **K1:** the top 5's newer-half median `mfe60` is above the bottom 5's.
- **K2:** the top 5's newer-half runner rate is above the bottom 5's.

Manual inspection happens afterward to catch bugs. It is not a gate.

## Verdict rules

| Verdict | Rule |
|---|---|
| **INCONCLUSIVE** | Spend gate failed, or fewer than 30 included actors, or actors from fewer than 6 events. |
| **PASS** | Correlation at least 0.25, P1 at least 95%, R1, R2, and R3 pass, and K1 and K2 hold. |
| **PROMISING** | P1 at least 90%, but a PASS condition fails. |
| **FAIL** | P1 below 90%, and S1 below 95%. |
| **PROMISING** (second route) | P1 below 90%, but S1 at least 95%. |

**Consequences:**

- **PASS:** build Déjà View around Launch Reflex. Reflex = shrunk mean `mfe60` over prior launch
  entries, with runner rate and failed-launch rate beside it, described as opportunity recognition.
- **PROMISING:** build Launch Reflex, labeled experimental in the product and README.
- **FAIL:** Launch Reflex is dead. Pivot to event-pattern matching only.
- **INCONCLUSIVE:** stop and report. No further spend without a user decision.

## Budget

**Hard cap:** 6,000 credits from the D3 start balance, enforced in code.

| Stage | Estimate |
|---|---|
| 1. Screener pages | 50 to 200 |
| 1–2. Eligibility and actor buys | 150 to 300 |
| 3. Wallet history (about 120 wallets × 3) | 360 |
| 4. T0 resolution (about 600 tokens × 2) | 1,200 |
| 4. Prices (about 800 entries × 3.5) | 2,800 |
| **Total** | **about 4,500 to 4,900** |

**Stop rule:** if Stage 4 spend would pass the cap, finish the current actor and stop. Analysis uses
completed actors. Fewer than 30 included actors makes the verdict INCONCLUSIVE.

## Known limits D3 does not fix

1. Pump.fun only.
2. The whole-day-age pre-filter can drop real launch entries.
3. High-frequency wallets fill 1,000 rows in days, so entries cover a short period.
4. Nansen can restate historical data.
5. `P0` is a 2-minute median during the most volatile minutes of a token's life.
6. The screener's own coverage of dead tokens is unverified beyond the Stage 1 validation.

## Amendment 1: sample-size protection (frozen before any outcome data)

**Made:** 2026-09-14, after Stages 1–3 and before Stage 4. No outcome metric had been fetched or inspected.
**Reviewed by:** Codex. **Approved by:** the user.

**Why:** Stages 1–3 produced exactly the minimum, 6 events and 30 actors. Normal attrition in Stage 4
would likely make the verdict INCONCLUSIVE.

**Rule:**

1. Extra dates are each original date plus exactly 3 days, processed in this order:
   2026-06-13, 06-20, 06-27, 07-04, 07-11, 07-18, 07-25, 08-01, 08-08, 08-15. No substitutions.
2. For each extra date, run Stage 1 (event and actor selection), then Stage 3 (history, gate, merge),
   with the same rules as the original dates.
3. Stop adding dates as soon as at least 40 independent actors pass the 20-candidate gate after merging,
   or after all 10 extra dates.
4. Then run the spend gate, Stage 4, and Stage 5 unchanged.
5. The 6,000-credit hard cap from the D3 start balance is unchanged.
6. The minimum of 30 included actors is unchanged. If attrition still leaves fewer than 30, the verdict
   is INCONCLUSIVE, which is evidence that Launch Reflex needs more data than the product can supply.
