# Next session: art assets, polish, demo, submission

**Written:** 2026-09-15, end of a long session. Submit by 2026-09-26.

## Read first

1. `docs/FINAL_PLAN.md`: the Launch Rewind decision and schedule. The look has since become the **Launch Party**.
2. `docs/ART_ASSET_BRIEF.md`: the art the user is generating, and how to wire it in.
3. `docs/reviews/`: Grok's product review and the competition scan.
4. `README.md` is out of date. It still describes the old scan page and lookalike matching as the headline.

## What the product is now

**Déjà View: same faces, different launch.** Paste a pump.fun token. The page replays the launch's first hour as a party:
the 8 biggest buyers queue at the club door in arrival order, each as a generated character. As the replay runs, each buyer
resolves to a tier from Launch Reflex: VIP (95+, gold), strong record (60+, cyan), known (grey), new face (dashed).
**Echoes** show earlier launches that two or more of today's buyers were also early on, with violet arcs on the timeline.

## State

| Item | Status |
|---|---|
| Launch Reflex scan | Working, validated in D3 |
| Buy timing, volume tape, echo detection | Working (`reflex.py`: `tape`, `echoes`) |
| Saved replays | Every finished live scan saves to `spike_out/scans/`. `?replay=1` replays without API calls. |
| Public mode | `DEJAVIEW_PUBLIC=1` replays from `data/replays/` only. Not deployed. `data/replays/` is empty. |
| Party page | `web/index.html`: code-drawn scene and characters, replay strip, answer, buyers, echoes, drawers, share card |
| Test hook | `?token=...&replay=1&at=1500` jumps the replay to a second, for headless screenshots |
| Lookalike matching | Demoted behind "Similar past setups →" |
| API usage proof | `tools/api_usage.py`. About 20,000 successful calls. |
| Credits | 711 left on 2026-09-16. A scan costs 300 to 500: the more launch history the buyers have, the dearer it is. |

## Next steps, in order

1. **Done 2026-09-15: art wired in.** `tools/build_art.py` turns `web/art/raw/` into `web/art/` (WebP plus
   `manifest.json`). The page uses the painted club, bouncer, guests, and head avatars, and falls back to the
   code-drawn scene per image. All 24 guests are used, and buyers at one launch always get different faces.
   Raw PNGs are not committed. The user rejected likeness worries about the bouncer and the plant creature: use all art.
2. **Done 2026-09-16: the club moves.** `tools/build_art.py` also turns `web/art/raw/club-loop.mp4` and
   `bouncer-loop.mp4` into seamless loops (forward then backward, because a cross-fade ghosts the painted signs).
   The bouncer is a transparent WebM, so Safari and reduced-motion get the stills instead. Source clips are not committed.
3. **Phone layout is still broken:** the page is wider than the screen and the lineup overflows the scene. Fix before submitting.
4. **Done 2026-09-16: 4 demo launches saved** in `data/replays/`: PAID (best: 4 of 8 strong, 3 shared FLAME which
   then did 10x), BRAIN, PVE, and ELON (7 of 8 buyers shared earlier coins, but those coins barely moved).
   **Picking demo coins:** the screener's 24-hour volume says nothing about the first hour. Check the first hour
   directly with `Scanner.first_hour_buys` (about 4 calls) and look for 6+ buyers over $500 with a spread of sizes.
5. **Done 2026-09-16: live at https://dejaview-delta.vercel.app** (Vercel, free, static). `tools/build_static.py`
   writes `dist/` and `cd dist && vercel deploy --prod` publishes it. The link is on every share card via
   `SITE_URL` in `web/index.html`. The Render blueprint below still works if the Python app is ever wanted.

   **Old note, Render.** `render.yaml` is committed and sets `DEJAVIEW_PUBLIC=1`, so the site replays saved launches
   only and never calls Nansen. The repo is public at **https://github.com/stevehq26-bot/dejaview**. No Render
   credentials exist on this machine, so the owner must click once:
   **https://render.com/deploy?repo=https://github.com/stevehq26-bot/dejaview**
   Afterwards, set `SITE_URL` in `web/index.html` (it prints on every share card) and add the link to the README.
   A fresh clone was tested on 2026-09-16: venv, install, `DEJAVIEW_PUBLIC=1 python app.py`, all four replays serve.
6. **Done 2026-09-16: README rewritten** around the product, with the no-key path, the live-scan path and cost, the
   endpoint-to-feature table, the usage receipt, and how to verify the claims.
7. **Record the silent demo** (30–45 seconds) and submit.

## Corrections made on 2026-09-16 (judge-style review)

A judge-style review found the headline echo claim was wrong. Fixed:

1. **Echoes now use the same launch-window rule as scoring.** They used a loose age prefilter, so a buy 25 h after a
   launch counted as "early". PAID's FLAME claim was 3 buyers; only 2 qualified. Its verified top echo is now
   **EMBER, 3 buyers, all inside 1.3 h, which then moved 10x**. Unresolvable launches are left out, not counted.
2. **Missing data no longer reads as "New face."** States: history unavailable, no price data, too little history,
   or checked and nothing found. The headline counts only buyers we could check.
3. **Characters are stable again.** The face comes from the wallet alone; duplicates in one lineup show addresses.
4. `tools/recompute_replays.py` fixed the saved replays from cached data, no API calls. `tools/test_claims.py`
   runs offline and would have caught the original error.

**Still open from that review:** scoring's candidate prefilter still uses today's date (`plausible_launch(v, now)`),
so a rescan on a later day can drop candidates; cached history reads do not apply the lower 30-day bound; the page
ignores `first_hour_complete`, so a launch less than an hour old would still be narrated as a full hour; metric
labels ("92" is a reference percentile, "high confidence" means 16+ entries, echo moves are the best among priced
participants) need plainer wording. The official deadline is **2026-09-27 23:59 UTC**, and Nansen expects live data
visible in the recording, so a replay-only video may not satisfy them: check with the organisers.

## Price line (2026-09-16)

`/api/v1/tgm/token-ohlcv` at 1-minute candles costs 1 credit per launch and gives the first hour's closing prices.
`launch_data.price_minutes()` fetches it, the scan stores it in the tape as `price_s_usd`, and
`tools/backfill_prices.py` added it to the four saved replays. The timeline and the share card draw it green when
the hour ended up, red when it ended down. It describes the hour; it is not a forecast.

## Music credit (must appear in the README and the X post)

**"Neon Synthwave Vibe" by Lumen Sound**, from Pixabay (file 554114). Free for commercial use, no attribution
required, but credit it anyway. The track is registered with YouTube Content ID; the licence certificate is saved
at `docs/licences/neon-synthwave-vibe-pixabay.txt`, which is what answers a claim on the recording.

## Working agreements with this user

- Replies use the four-line format in the user's global `CLAUDE.md`. Plain words.
- Before a large spend, write the rules down and let the user pass them to Codex. Grok runs locally: `~/.grok/bin/grok`,
  headless with `--prompt-file` and `--permission-mode plan` (read-only; it stops if it wants to run code, so give it the data).
- Never claim: smart money, proven, profitable, coordinated, insider, predictions, or probabilities. Echoes show repeated
  behaviour, not connected wallets.
- No copyrighted meme characters (the mockup used Pepe; the product must not).
- Port 8420 is Déjà View. Port 8787 belongs to another app. The Déjà View server may already be running under `nohup`.
- Commit in small steps. Never commit `spike_out/` or `.env`.

## Known issues

- The replay animation uses `requestAnimationFrame`; headless Chrome renders few frames, so use `&at=` for screenshots.
- The queue in the scene overlaps when buyers arrive close together.
- Mobile layout is untested for the party page.
- Scores can shift on a rescan when an earlier price request failed.
