# Next session: demo, polish, and submission

**Written:** 2026-09-14, after the corpus and matching were built.

## Read first

1. `README.md`: what exists, Launch Reflex, and the "we've seen this before" matching.
2. `spike_results.md`, the last three sections: corpus freeze, collection, and backtest results.
3. `docs/CORPUS_PLAN.md`: frozen matching rules and Amendment 1.
4. `docs/DEJA_VIEW_CLAUDE_CODE_MASTER_PLAN.md`, sections 15, 16, 17, 19, and 25: screens, demo, README, schedule, and definition of done.

## State

| Item | Status |
|---|---|
| Spike | Done. GO. |
| Launch Reflex scan | Working. Live and replay. |
| Event fingerprint and matching | Working in the scan, the terminal, and the web page. |
| Corpus | 31 events in `data/corpus.json`. Backtest verdict SIGNAL (ρ = 0.57), driven mostly by concentration. |
| Demo recording | Not started |
| API calls | About 19,500 successful, counted from the log rows. The competition needs 1,000. |
| Credits | About 4,020 |
| Deadline | Submit by 2026-09-26 |

## What to do next

1. **Look at the screen in a browser.** The page logic was checked, and the scan stream carries the matching
   section, but nobody has viewed the new section on screen yet.
2. **Pick demo launches.** One replay with a clear match and a counter-example, and one live pump.fun launch more
   than an hour past its launch moment. Corpus tokens are excluded from their own matches.
3. **Verification command** for API usage (master plan section 13): total and successful requests, endpoint
   breakdown, credits, and first and last timestamps from `spike_out/calls.jsonl`.
4. **Clean-clone test:** a fresh clone, setup, and one cold scan in under 10 minutes.
5. **Recording** that makes sense muted, then README demo link and submission.

## Working agreements with this user

- Replies use the four-line format in the user's global `CLAUDE.md`. Plain words, no jargon.
- Before a large spend, write the rules down and let the user pass them to Codex for review.
- Freeze pass rules before fetching outcome data. Log every amendment in `spike_results.md`.
- Commit in small steps. Never commit `spike_out/` or `.env`.
- Port 8787 belongs to another app of the user's. Déjà View uses 8420.

## Known issues

- Old copies of `app.py` may still be running on port 8420 with pre-matching code. Restart the app to see matching.
- The running call total in `calls.jsonl` is wrong when two app copies write at once. The verification command must count successful rows, not read the last total.
- A full cold scan from a fresh clone has not run end to end yet.
- Scores can shift on a rescan when an earlier price request failed.
- The historical screener returns next-day tokens on some dates (2026-08-05, 08-08, 08-15).
- Many corpus buyers are fresh wallets with no history, so about 1 in 4 sampled events had no fingerprint.
