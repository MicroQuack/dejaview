# Déjà View corpus and matching: rules for review

**Version:** 1, draft 2026-09-14. **Status:** not frozen. No corpus data has been fetched.
**Author:** Claude Code. **To review:** Codex. **To approve:** the user.

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
| Launch Reflex | The live scan's score for a buyer, a percentile from 0 to 100, computed only from trades before T0 |
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
or when all 3 rounds finish. If collection stops inside a round, then later dates in that round have one
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
| **Actor quality** | Mean Launch Reflex of scoreable top buyers, weighted by each buyer's first-hour buy USD |
| **Entry speed** | Median minutes from T0 to the first buy of scoreable top buyers with Launch Reflex of 50 or more, clipped to 0 to 60. If there are none, then 60. |
| **Persistence** | Share of the top buyers' first-hour buy USD that falls in windows after each buyer's first window |
| **Concentration** | Share of all buyers' first-hour buy USD that comes from the 3 largest buyers |

**Fingerprint requirement:** at least 3 scoreable top buyers. An event with fewer is recorded with its
counts and left out of matching. A live launch with fewer gets the message "Too few known buyers to find
similar launches."

**Notes on the definitions:**

- Entry speed uses 60 when no strong buyer arrives, because "no strong buyer in the first hour" is the
  slowest possible arrival. A buyer who entered before T0 counts as 0 minutes.
- Launch Reflex of 50 means the buyer ranks above half of the D3 reference buyers.
- Persistence ignores buyers outside the top 8, so a burst of late small buyers does not inflate the value.

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

1. Standardize each feature with the corpus mean and standard deviation.
2. Distance is Euclidean over the 4 standardized features, with equal weights.
3. Show the 3 nearest corpus events, nearest first. Each card shows the features that matched closest,
   and the outcome at 6 h, 24 h, and 7 d.
4. If all 3 are winners, or if all 3 are losers, then add a fourth card: the nearest event with the other
   result, labeled "Nearest counter-example".
5. Never exclude the event being scanned by outcome. Exclude it only when it is itself a corpus token.
6. A live launch gets matching only after its decision point.

## Backtest: do nearby launches share outcomes?

**This test is not a gate on shipping.** It decides what the README and the screen are allowed to say.

**Method, leave one out.** For each corpus event:

1. Find its 3 nearest other events, excluding events from the same sample date. Same-date launches share
   market conditions, which would inflate the result.
2. Take the mean `ret24h` of those 3 events.

**Statistic:** Spearman correlation across events between each event's own `ret24h` and its neighbours'
mean `ret24h`.

**Null:** keep every neighbour list fixed. Shuffle `ret24h` values across events, 5,000 times, seed
20260914. Recompute the statistic each time. The percentile is the share of shuffles with a lower statistic.

**Reported only:** the same test for `ret6h` and `ret7d`, and the test for each single feature alone.

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
reaches 11,400, which keeps 600 for Stage 3.

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

## Questions for the reviewer

These are the judgement calls in this draft. Each has a reason above.

1. Returns start at the decision point, T0 + 1 h, not at T0 as the brief said.
2. Entry speed uses 60 minutes when no buyer has Launch Reflex of 50 or more.
3. The fingerprint needs at least 3 scoreable top buyers.
4. Up to 3 events per date across 20 dates, instead of more dates with 1 event each. This choice reuses
   cached screener results and T0 lookups.
5. The counter-example card appears only when the 3 nearest events all have the same 24 h result.
6. The backtest excludes same-date neighbours, and it keeps neighbour lists fixed while it shuffles outcomes.
7. The backtest is not a gate on shipping. It controls only the wording.
8. The budget cap is 12,000 credits of about 16,200, which leaves about 4,000 for the demo and checks.

## Known limits

1. Pump.fun only, and the dates run from 2026-06-10 to 2026-08-15. Market conditions in September can differ.
2. Launch Reflex percentiles come from the 37 D3 reference buyers. Some corpus buyers are those same buyers.
   This affects the scale of actor quality, not its order.
3. Up to 3 events per date share market conditions. The backtest excludes same-date neighbours for this reason.
4. Fifty events is a small corpus. The nearest analogue can still be far away. The screen shows the distance
   as "close", "moderate", or "distant", using the corpus's own distance terciles.
5. Nansen can restate historical data.
