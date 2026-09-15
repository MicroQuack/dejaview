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
| Credits | About 3,000 |

## Next steps, in order

1. **Done 2026-09-15: art wired in.** `tools/build_art.py` turns `web/art/raw/` into `web/art/` (WebP plus
   `manifest.json`). The page uses the painted club, bouncer, 23 guests, and head avatars, and falls back to the
   code-drawn scene per image. All 24 guests are used, and buyers at one launch always get different faces.
   Raw PNGs are not committed. The user rejected likeness worries about the bouncer and the plant creature: use all art.
2. **Pick 3 demo launches** with a strong echo. Scan them live, then copy their saved scans into `data/replays/`.
3. **Deploy on Render** in public replay mode. Codex's `render-deploy` skill pattern: add a `render.yaml`, push to GitHub
   (the `gh` login works, but no remote exists yet), and give the user the Render dashboard link.
4. **Rewrite the README** around the party, echoes, and the evidence. Keep the honest claims.
5. **Record the silent demo** (30–45 seconds) and submit.

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
