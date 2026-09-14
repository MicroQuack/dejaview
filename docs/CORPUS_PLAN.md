# Déjà View corpus and matching: frozen rules

**Version:** 2, 2026-09-14. **Status:** frozen at 2026-09-14T17:45:53Z, before any corpus request.
**Author:** Claude Code. **Reviewed by:** Codex. **Approved by:** the user.

## Changes from version 1 after Codex review

| # | Change | Reason |
|---|---|---|
| 1 | Collection pauses at 30 fingerprinted events for a cost-only checkpoint. It continues to 50 only if 4,000 credits would remain. | 50 events could cost most of the balance. The decision uses cost, not results. |
| 2 | The backtest excludes neighbours with sample dates within 7 days, not only the same date. | Sample dates are 3 to 4 days apart, and one market week can make both fingerprints and outcomes alike. |
| 3 | Before outcomes, drop any feature with an absolute Spearman correlation above 0.80 against a higher-priority feature. | Persistence can depend on entry speed. Redundant features would count twice. |
| 4 | Actor quality uses the underlying shrunk Reflex, weighted by the square root of buy USD. | The percentile depends on 37 reference buyers, and raw USD weights let one large buyer dominate. |
| 5 | A launch whose nearest match is farther than the 95th percentile of corpus nearest-neighbour distances gets "We haven't seen this one before." | A nearest-neighbour search always returns something, even when nothing is close. |
| 6 | The backtest learns the scale without the held-out event. | The test is then fully leave one out. |

This document fixes how Déjà View builds its library of past launches, how it describes each launch,
how it finds similar past launches, and how it checks whether those matches mean anything. The rules
freeze before the first corpus request. Nothing below changes after outcome data arrives.

## What the feature claims

> For a new pump.fun launch, at one hour after its launch moment, these are the past launches whose
> first-hour buyers looked most alike, and this is what happened to those launches next.

It shows observed past cases, winners and losers. It never shows a probability.

## Terms

| Term | Meaning |
|---|---|
| T0 | First time cumulative DEX volume after deployment reaches $5,000, one count per transaction (unchanged from the spike) |
| Decision point | T0 + 1 hour. Every fingerprint feature is known at this time. |
| Buyer | A wallet with buys of at least $500 from deployment to T0 + 1 hour, after the label and 25-buy filters |
| Top buyers | The 8 buyers with the largest total buy USD (the live scan's rule) |
| Launch Reflex | The live scan's score for a buyer, computed only from trades before T0. The underlying value is the shrunk mean `mfe60`. The screen shows it as a percentile of the D3 reference buyers. |
| Scoreable buyer | A top buyer with at least 3 priced prior launch entries (the live scan's rule) |
| Event | One sampled launch |
| Corpus | The library of events with a fingerprint and outcomes |

## Stage 1: sample events

**Source:** `/api/v1beta1/token-screener/historical`, the D3 request per date, unchanged.

**Dates:** the 20 D3 dates, in calendar order: 2026-06-10, 06-13, 06-17, 06-20, 06-24, 06-27, 07-01,
07-04, 07-08, 07-11, 07-15, 07-18, 07-22, 07-25, 07-29, 08-01, 08-05, 08-08, 08-12, 08-15.
Fourteen screener results are already cached from D3. Six dates need new screener requests.

**Candidate order per date:** pump.fun addresses, sorted by `sha256(token_address + date)`. This is the
D3 order, so cached T0 lookups are reused.

**Eligibility, checked in candidate order.** A candidate becomes an event when all of these hold:

1. Deployment, from `tgm/token-information`, is on the sample date, UTC.
2. T0 is within 6 hours of deployment.
3. At least 6 buyers pass the buyer rule.

**Differences from D3 event selection:**

- D3 dropped wallets already used in an earlier event. The corpus keeps all wallets, because the
  live scan keeps all wallets. D3 events are re-selected under this rule, not copied, so a D3 token
  becomes a corpus event only if it passes in its own turn.
- D3 took one event per date. The corpus takes up to 3 per date.

**Rounds.** Round 1 takes the first eligible candidate on each date, in calendar order. Round 2 takes the
second eligible candidate on each date, continuing in hash order. Round 3 takes the third. Rounds spread
the corpus evenly across dates if the stop rule ends collection early. Each date checks at most 30
candidates in total. Each event is fingerprinted as soon as it is selected, before the next date.

**Stop rule.** Stop as soon as 50 events have a fingerprint, or when the budget stop in "Budget" applies,
or when the checkpoint at 30 events stops collection, or when all 3 rounds finish. If collection stops inside a round, then later dates in that round have one
fewer event. The count per date is reported.

**API failures.** Retry a failed request up to 3 times. If a candidate still fails, then record it as
skipped for API failure, and move to the next candidate. If a scored event has a buyer whose history,
T0 lookup, or price request failed, then rerun that event from cache up to 2 more times. After that,
accept the event and record the failure count.

## Stage 2: fingerprint each event

For each event, run the live scan's code, `reflex.Scanner`, with the event's T0 as the cutoff. Corpus
events and live scans use the same functions, so the features mean the same thing in both.

**Buy windows:** `[deploy, T0 + 5 min]`, `[T0 + 5 min, T0 + 15 min]`, `[T0 + 15 min, T0 + 30 min]`,
`[T0 + 30 min, T0 + 60 min]`. A buy that appears on a shared edge counts once, in the earlier window.

| Feature | Definition |
|---|---|
| **Actor quality** | Mean underlying Launch Reflex of scoreable top buyers, weighted by the square root of each buyer's first-hour buy USD |
| **Entry speed** | Median minutes from T0 to the first buy of strong buyers, clipped to 0 to 60. A strong buyer is a scoreable top buyer whose underlying Launch Reflex is above the median D3 reference buyer. If there are none, then 60. |
| **Persistence** | Share of the top buyers' first-hour buy USD that falls in windows after each buyer's first window |
| **Concentration** | Share of all buyers' first-hour buy USD that comes from the 3 largest buyers |

**Fingerprint requirement:** at least 3 scoreable top buyers. An event with fewer is recorded with its
counts and left out of matching. A live launch with fewer gets the message "Too few known buyers to find
similar launches."

**Notes on the definitions:**

- Entry speed uses 60 when no strong buyer arrives, because "no strong buyer in the first hour" is the
  slowest possible arrival. A buyer who entered before T0 counts as 0 minutes.
- A strong buyer is one whose displayed Launch Reflex is 50 or more. Matching uses the underlying value.
- Matching never uses the displayed percentile.
- Persistence ignores buyers outside the top 8, so a burst of late small buyers does not inflate the value.

**Checkpoint at 30 fingerprinted events, before any outcome:**

1. Credits per event = corpus spend so far ÷ fingerprinted events.
2. Projected spend = spend so far + credits per event × 20 + 8 credits × 50 for outcomes.
3. If the start balance minus projected spend is at least 4,000, then continue to 50. Otherwise, stop at 30.

The checkpoint also reports the feature correlations. It uses no outcome data.

**Feature redundancy, when Stage 2 stops and before any outcome:**

1. Priority order: actor quality, entry speed, concentration, persistence.
2. Compute Spearman correlations between features across all fingerprinted events.
3. Walk the features in priority order. Keep a feature unless its absolute correlation with an already kept
   feature is above 0.80.
4. Matching, the backtest, and the screen's "matched on" lines use only the kept features. The screen still
   shows all four values.

## Stage 3: outcomes

Outcomes run only after Stage 2 has stopped for every event. Stage 2 decisions, including any budget
change, happen before any outcome is visible.

**Prices** use `launch_data.price_at`: the median of the first trades in `[t, t + 1 h]`. If there are
none, then the last trades in the day before `t`. If there are still none, then the price is 0, which
means the token has no trades.

| Quantity | Time |
|---|---|
| Base price | Decision point, T0 + 1 h |
| `ret6h` | Decision point + 6 h |
| `ret24h` | Decision point + 24 h |
| `ret7d` | Decision point + 7 d |

**Returns are measured from the decision point, not from T0.** The brief said "T0 to +6 h". A user acts at
T0 + 1 h, and the fingerprint describes buying inside the first hour. A return that starts at T0 would
include the price move that the fingerprint's own buyers caused. That return would make matching look
better than it is.

- For the test: capped log return, `ln(P / base)` limited to `[−ln 10, +ln 10]`. A price of 0 scores `−ln 10`.
- For display: percent change. A price of 0 shows as "−100%, no trades".
- **Winner** means `ret24h` above 0. **Loser** means `ret24h` at or below 0.
- An event without a base price has no outcomes and is left out of matching. The count is reported.

## Matching

1. Standardize each kept feature with the corpus mean and standard deviation.
2. Distance is Euclidean over the standardized kept features, with equal weights.
3. Show the 3 nearest corpus events, nearest first. Each card shows the features that matched closest,
   and the outcome at 6 h, 24 h, and 7 d.
4. If all 3 are winners, or if all 3 are losers, then add a fourth card: the nearest event with the other
   result, labeled "Nearest counter-example".
5. Never exclude the event being scanned by outcome. Exclude it only when it is itself a corpus token.
6. A live launch gets matching only after its decision point.
7. **Closeness.** For each corpus event, compute its distance to its nearest other event, with the scale
   learned without it. A match at or below the median of those distances is "close". A match at or below
   the 95th percentile is "moderate". A farther match is "distant".
8. **Not seen before.** If the nearest match is distant, then the screen says "We haven't seen this one
   before. No close historical analogue yet." It shows the nearest launches below that, for context only.
9. Each card shows how many of the top buyers were scoreable, for both the live launch and the past launch.

## Backtest: do nearby launches share outcomes?

**This test is not a gate on shipping.** It decides what the README and the screen are allowed to say.

**Method, leave one out.** For each corpus event:

1. Learn the mean and standard deviation of each kept feature from the other events only.
2. Find its 3 nearest events, excluding events whose sample date is within 7 days of its own. Launches from
   the same market week share conditions, which would inflate the result.
3. Take the mean `ret24h` of those 3 events.

**Statistic:** Spearman correlation across events between each event's own `ret24h` and its neighbours'
mean `ret24h`.

**Null:** keep every neighbour list fixed. Shuffle `ret24h` values across events, 5,000 times, seed
20260914. Recompute the statistic each time. The percentile is the share of shuffles with a lower statistic.

**Reported only:** the same test for `ret6h` and `ret7d`, and the test for each kept feature alone.

The live product matches against the whole corpus. The 7-day exclusion applies to the backtest only.

| Verdict | Rule | What Déjà View may say |
|---|---|---|
| **SIGNAL** | Correlation above 0 and percentile at least 95% | "In a backtest on past launches, launches with similar first-hour buyers tended to have similar next-day outcomes." The effect size is stated. |
| **NO SIGNAL SHOWN** | Anything else | "Similar past launches, for context. In our backtest, similarity did not predict what happened next." |

Both verdicts ship the matching screen. Neither verdict allows a probability.

## Budget

**Start balance:** read from the call log before the first corpus request. About 16,200 credits today.

**Measured costs:** the two cold scans on 2026-09-14 used 329 and 257 credits.

| Stage | Estimate |
|---|---|
| Screener, 6 new dates | Up to 120 |
| Eligibility checks and buyer requests | About 1,500 |
| Scans, 50 events, less shared caches | About 9,000 to 12,000 |
| Outcomes, 4 prices per event | About 400 |
| **Total** | **About 11,000 to 14,000** |

**Hard cap:** 12,000 credits from the start balance, enforced in code. Stage 2 stops when its spend
reaches 11,400, which keeps 600 for Stage 3. The checkpoint at 30 events can stop collection earlier.

**If the cap stops Stage 2 before 50 events:** the user may buy credits and raise the cap. Because no
outcome data exists at that point, raising the cap is not a rule change. It is logged as an amendment.

**Minimum:** matching ships with at least 30 fingerprinted events with outcomes. If there are fewer, then
the corpus work stops, and the result goes to the user.

## Storage

`data/corpus.json` goes in the repository. It holds derived data only: sample date, token address,
symbol, deployment, T0, the 4 features, buyer counts, outcomes, and fetch time. It holds no wallet
addresses and no raw trades. Raw responses stay in `spike_out/corpus/`, which git ignores.

## Implementation

`corpus.py` implements these rules, and `matching.py` holds the fingerprint and matching code that the live
scan also uses. Before collection, `corpus.py` copies D3 wallet histories into the scan's history cache.
D3 fetched the same 30-day windows before the same T0, so the copy changes cost, not results.

## Known limits

1. Pump.fun only, and the dates run from 2026-06-10 to 2026-08-15. Market conditions in September can differ.
2. Launch Reflex percentiles come from the 37 D3 reference buyers. Some corpus buyers are those same buyers.
   This affects the scale of actor quality, not its order.
3. Up to 3 events per date share market conditions. The backtest excludes neighbours within 7 days for this reason.
4. A corpus of 30 to 50 events is small. The "not seen before" rule covers launches unlike any of them.
5. Nansen can restate historical data.

## Amendment 1: budget raise to reach the minimum (made before any outcome data)

**Made:** 2026-09-14T19:04:05Z, after Stage 2 stopped on budget and before Stage 3. No outcome had been fetched or inspected.
**Approved by:** the user. This is the budget raise that "If the cap stops Stage 2 before 50 events" allows.

**Why:** the budget stop left 29 fingerprinted events, one below the minimum of 30. One missing base price
in Stage 3 would drop the corpus further.

**Rule:**

1. The hard cap rises from 12,000 to 13,500 credits. The Stage 2 stop rises from 11,400 to 12,900, which keeps 600 for Stage 3.
2. Collection resumes in the same order and stops as soon as 31 events have a fingerprint, or at the new Stage 2 stop.
3. The 30-event checkpoint does not apply. Its only possible result at this balance is to stop at 30.
4. The redundancy check reruns on all fingerprinted events when collection stops, before any outcome.
5. No credits are bought. Everything else is unchanged.
