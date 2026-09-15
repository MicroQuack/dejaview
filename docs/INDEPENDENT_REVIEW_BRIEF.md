# Déjà View: brief for an independent product review

You are reviewing a hackathon entry that works technically but does not yet feel like a product.
The builder's own view: "It is close to being something, but the main feature feels like a toy."
Be blunt. Say what to cut, what to keep, and what to build in the time left.

## The competition

- Nansen Meridian Buildathon. Submit by 2026-09-26 (11 days from 2026-09-15).
- Judged 25% each on data integration, creativity and originality, functionality, and documentation.
- Must use the Nansen API (1,000+ calls; this project has about 20,000), ship a working demo, and post
  a recording on X. Judges want creativity over complexity, and a demo that makes sense with the sound off.

## What exists today

A local web app. You paste a Solana pump.fun token address. It returns three things.

1. **Who is buying.** The 8 biggest buyers ($500+) in the token's first hour after its "launch moment"
   (the first time cumulative trading reached $5,000).
2. **Launch Reflex per buyer.** For each buyer, their earlier launch buys in the prior 30 days, and how
   often those tokens offered a strong move within an hour of the wallet's entry (the 5th-highest price in
   the hour versus the entry price). Shown as a 0–100 percentile against 37 reference buyers.
3. **"We've seen this before."** The launch gets a 4-number fingerprint (buyer quality, buying speed,
   buyer concentration, follow-through). The app shows the 3 nearest launches from a library of 31 sampled
   past pump.fun launches, plus a counterexample when all 3 went the same way, with their price change
   6 hours, 24 hours, and 7 days after their first hour.

## The evidence so far

| Claim | Test | Result |
|---|---|---|
| Launch Reflex measures something real | Pre-registered retest: 40 buyers across 8 random launches. Does a wallet's score on older launches predict its score on newer ones? | **Passed.** Rank correlation 0.42, stronger than 99.6% of random shuffles. Survived removing each launch, dropping each wallet's best trade, and controlling for market week and entry speed. Moderate effect. |
| Similar launches have similar outcomes | Pre-registered leave-one-out backtest on the 31-launch library, excluding neighbours from the same week | **Passed the rule** (rank correlation 0.57, 99.9%), but **almost all of it came from one feature, buyer concentration**, which mostly reflects how many buyers a launch had. Buyer quality alone had no predictive value for launch outcomes. |

## Facts that make the matching feature weak

- **Base rate:** only 4 of the 31 library launches were up 24 hours later. The median launch was down 57%.
- **The same few launches keep appearing.** Across all 31 launches used as queries, one launch appeared as a
  nearest match 8 times, and the "counterexample" card came from the same 4 winners every time (one of them 10 times).
- **The library is small and old:** 31 launches from 2026-06-10 to 2026-08-15. About 1 in 4 sampled launches
  could not be fingerprinted because their big buyers were fresh wallets with no history.
- **Cost:** each new library launch costs about 250–500 Nansen credits. About 3,000 credits remain. More can be
  bought (about 24,000 credits for $12).
- **Matches are rarely "close":** of 93 nearest-match cards, 38 were labelled close, 54 moderate, 1 distant.

## Data and endpoints available

| Nansen endpoint | Gives | Credits |
|---|---|---|
| `tgm/dex-trades` | Every trade for a token in a time window, with trader address, labels, USD value, price | 1 |
| `tgm/token-information` | Deployment time, symbol | 1 |
| `profiler/dex-trades` | A wallet's trades in a time window (1,000 rows per call) | 1 |
| `token-screener` | Current tokens by volume, age, liquidity | 1 |
| `token-screener/historical` | Point-in-time token lists for past dates | 5 |

Also cached locally: about 170 wallet histories, a few thousand token launch moments, and prices for about 2,000 launch entries.

Nansen's free web app opens wallet and token pages without sign-in, so the app can link out to them.

## Screenshots to look at

Attach these: the home page, a full scan result (BRAIN), and the "We've seen this before" section (NINA).

## Questions to answer

1. As a pump.fun trader, would you open this during a launch? What single answer would make you open it?
2. Is Launch Reflex (the validated part) the real product, with matching as a side feature? Or is there a way
   to make matching the unique selling point honestly, given the base rate and small library?
3. What is the most original and demo-able product you can build from this data in 11 days with about
   3,000 credits (or about 27,000 after a $12 top-up)? Examples to accept or reject: a live feed of new launches
   that auto-flags strong buyers, a leaderboard of top Launch Reflex wallets and what they bought today,
   "these same wallets were early on X and Y" links between launches, a watchlist, a shareable scan card.
4. What should be cut from the current screen?
5. What claims must the product avoid, given the evidence above?
6. Give a ranked build plan: must-have, should-have, skip.
