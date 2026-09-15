# Déjà View: final build plan to submission

**Written:** 2026-09-15, after two independent reviews (Grok, ChatGPT) and a scan of other entries.
**Status:** proposed, waiting for the user's approval.

## What the competition rewards

- Nansen's own words on the campaign page: "We've seen dashboards. Show us something we haven't."
- Past Nansen contest winners had a working loop, a new angle on the data, or something unexpected, such as a
  game or a physical object. Dashboards alone did not win.
- A 30–60 second demo that makes sense with the sound off.

## What other builders have shown (day 2 of 14)

| Entry | What it is |
|---|---|
| Smart Money Shell, Aquarium, Thesis Desk | Nansen's own sample projects |
| ProofPulse, id8, Glass Knot | Smart money investigation and "is this a buy?" tools |
| Nansen Time Machine | A buy, pass, or short game on past Ethereum snapshots |
| The Undertaker | A Telegram chat bot for wallet and token cards |
| Wallet Tinder (concept) | Swipe wallets; flag when good wallets pile into a token |
| Syndicate Dossier, CoinEasy brief | Wallet archetypes; a daily research brief |

**Crowded:** smart money terminals, chat bots, wallet profiles, and "good wallets are buying" alerts.
**Nobody has:** pump.fun launches at minute level, or a wallet skill score measured on launches and tested before use.

## The decision

**Déjà View becomes "Launch Rewind": replay the first hour of a pump.fun launch and see which buyers we've seen before.**

- It is not a wallet tracker. The subject is one launch, told as a story in time.
- It uses the part that passed a frozen test: Launch Reflex.
- The name still fits: déjà vu about wallets, not about chart shapes.
- The lookalike-launch matching is cut from the main screen. It stays in the research log and behind one link.

## What the screen does

1. **The rewind.** A timeline from deployment to one hour after the launch moment. Each big buy appears at its
   real second, sized by dollars. As the replay runs, each buyer's dot resolves: cyan for a better launch record
   than most, grey for an ordinary record, hollow for a fresh wallet. Strong buyers are labelled with their score.
2. **The answer.** One sentence when the replay ends: "6 of the 8 biggest early buyers have a better launch record
   than most. The first arrived 16 minutes in."
3. **Seen before.** Click a strong buyer to see their earlier launches and how far each moved within an hour. Where two
   or more of this launch's buyers were early on the same earlier coin, the screen says so: "3 of these buyers were also
   early on CHILLDOG." It does not claim the wallets are connected.
4. **Share card.** One button saves a picture of the rewind and the answer for an X post.

## Schedule

| Date | Work | Credits |
|---|---|---|
| 16–17 Sep | Rewind timeline, using buy timestamps the scan already fetches | 0 |
| 18 Sep | Seen before: receipts per buyer and shared earlier launches | 0 |
| 19 Sep | Answer sentence, cut matching to a link, simplify cards | 0 |
| 20 Sep | Share card | 0 |
| 21–22 Sep | Pick 3 demo launches, one live; rescan; README rewrite; fresh-clone test | about 1,200 |
| 23 Sep | Record the silent demo, watch it muted, fix what is unclear | about 300 |
| 24–25 Sep | Buffer and polish | — |
| 26 Sep | Submit | — |

**Total new credits: about 1,500 of the 3,000 left. No top-up needed.**

## Claims to avoid

Never say: profitable wallets, smart money, this will pump, any probability, or "similar launches predict this one".
Say: "has been early on launches that then offered a strong first-hour move, more often than most launch buyers."

## Risks

- **Wallet Tinder overlaps "good wallets piling in".** The difference to show on screen: a launch replay in time, and a
  skill score measured on launches and tested before use, not labels or profit.
- **Shared earlier launches may often be empty.** The screen then says "No shared launch history" and the demo uses a launch
  where it is not empty.
- **Busy launches have more than 1,000 first-hour buys of $500 or more.** The timeline then shows the largest 1,000 and says so.
