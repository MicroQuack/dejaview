# Next session: build Déjà View matching

**Written:** 2026-09-14, at the end of the spike and first product slice.

## Read first

1. `README.md`: what exists and how Launch Reflex works.
2. `spike_results.md`, sections "D3 results" and "Go/No-Go": the evidence and the frozen product definition.
3. The master plan, `DEJA_VIEW_CLAUDE_CODE_MASTER_PLAN.md`, sections 7, 8, 15, and 16. It is not in the
   repo. Ask the user to paste it or save it to `docs/`.

## State

| Item | Status |
|---|---|
| Spike | Done. GO. |
| Launch Reflex scan (`reflex.py`, `app.py`, `web/index.html`) | Working. Live and replay. |
| Event fingerprint | Not started |
| Historical corpus | Not started. The D3 retest has 12 sampled events with enriched buyers in `spike_out/d3/`. |
| Analogue matching and "We've seen this before" screen | Not started |
| Demo recording | Not started |
| API calls | More than 7,000 successful. The competition needs 1,000. |
| Credits | About 16,500 |
| Deadline | Submit by 2026-09-26 |

## What to build

1. **Event fingerprint**, four features, all known at T0 + 1 hour:
   - **Actor quality:** size-weighted mean Launch Reflex of scoreable first-hour buyers.
   - **Entry speed:** how soon after T0 the above-average buyers arrived.
   - **Persistence:** whether first-hour buyers kept adding across the four first-hour windows.
   - **Concentration:** share of first-hour buy volume from the top 3 buyers.
2. **Corpus** of mechanically sampled past launches, using the D3 sampling rule
   (`token-screener/historical`, pump.fun, hash order). Store derived features and outcomes only.
3. **Outcomes per corpus event:** price change from T0 to +6 h, +24 h, and +7 d, from `tgm/dex-trades`.
4. **Matching:** standardize the four features, then list the 3 nearest corpus events by distance. Show
   winners and losers. No probabilities.
5. **Screen:** "We've seen this before." Three analogue cards: why each matched, and what happened next.

## First decision for the user: corpus budget

A cold scan costs about 300 credits. The plan's 50-event corpus would cost about 15,000 credits,
nearly everything left. Options:

- **Reuse and extend.** Start from the 12 D3 events, which are already largely cached, and add events up to
  the budget. It is cheaper, but gives fewer analogues.
- **Buy more credits.** The last $12 bought about 24,000 credits. That funds the full 50-event corpus and
  leaves room for the demo.
- **Score fewer prior entries per buyer for corpus events.** Cheaper, but lower confidence on actor quality.

Recommend one option to the user with the cost, and ask before spending.

## Working agreements with this user

- Replies use the four-line format in the user's global `CLAUDE.md`. Plain words, no jargon.
- Before a large spend, write the rules down and let the user pass them to Codex for review.
- Freeze pass rules before fetching outcome data. Log every amendment in `spike_results.md`.
- Commit in small steps. Never commit `spike_out/` or `.env`.
- Port 8787 belongs to another app of the user's. Déjà View uses 8420.

## Known issues

- A full cold scan from a fresh clone has not run end to end yet. Setup and page load were tested.
- Scores can shift on a rescan when an earlier price request failed.
- TRUMP (`6p6x…GiPN`) is not a pump.fun launch. The app now warns on non-pump.fun tokens.
