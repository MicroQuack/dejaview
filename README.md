# Déjà View

**Same faces. Different launch.**

Paste a pump.fun token and Déjà View replays its first hour as a club night. The eight biggest
first-hour buyers arrive at the door in the order they bought, each as a character drawn from their
wallet address. As each one arrives, the page checks what that wallet did on earlier launches and
labels them: **VIP**, **strong record**, **known**, **new face**, or plainly **we could not check
this one**. When two or more of tonight's buyers were also early on the same earlier launch, that is
an **echo**.

**Watch it now: https://dejaview-delta.vercel.app** — five real launches, no sign-up, no API key.

Built for the Nansen Meridian Buildathon. Powered by the **Nansen API**.

## Demo

**[Watch the demo video on X](https://x.com/iAteUrSOL/status/2100539163883847883)**, posted by @iAteUrSOL. It runs
1:38 with captions, so it works with the sound off. It replays **PAID** from saved data, then runs a
live scan of **HYPED** against the Nansen API. That scan finds that 6 of HYPED's buyers were also
early on PAID.

## Watch it in two minutes, no API key

```bash
git clone https://github.com/MicroQuack/dejaview.git && cd dejaview
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py                 # then open http://localhost:8420
```

Click **PAID** in the "Replay a launch" row. Five saved launches replay from `data/replays/`
with no key and no API calls: **PAID**, **HYPED**, **ELON**, **BRAIN**, **PVE**.

**PAID is the one to watch.** Four of the five buyers we could check have a better launch record
than most, one of them ranks in the top 3%, and three of them were also early on **EMBER**, which
then offered a 10× move within an hour of their buys.

To serve replays only, so visitors can never spend your credits:

```bash
DEJAVIEW_PUBLIC=1 .venv/bin/python app.py
```

## Publish it

The public site needs no server at all. This writes `dist/`: the page, the art and the saved
launches as plain files, ready for any static host.

```bash
.venv/bin/python tools/build_static.py
```

The same `web/index.html` runs both ways: against the Python app locally, and against those files
when there is no scan API. `render.yaml` is also here if you would rather run the Python app itself.

## Scan a live launch, with your own key

```bash
cp .env.example .env                    # add NANSEN_API_KEY=...
.venv/bin/python app.py
```

Paste any pump.fun token address. A scan costs roughly **300 to 500 Nansen credits**, depending on
how much history its buyers have, and takes a few minutes. Every finished scan saves itself to
`spike_out/scans/`, and `?replay=1` replays it without spending anything again.

## What the words mean

- **Launch moment (T0).** The first time a coin's cumulative trading reaches $5,000.
- **The buyers.** The eight largest buyers of $500 or more in the hour after T0, excluding labelled
  exchange and bot addresses and wallets with more than 25 buys in that hour.
- **Launch Reflex.** For each buyer, we look at their launch entries in the 30 days before T0: buys
  that landed inside another launch's own six-hour window. We measure how often those launches went
  on to offer a strong move within an hour of the buy, then rank that against 37 reference launch
  buyers. **The score is a percentile, not a win rate, and not profit.** A 92 from five launches
  rests on less evidence than a 92 from sixteen, so the page always shows the count.
- **Echo.** An earlier launch that two or more of tonight's buyers were also early on, using that
  same six-hour rule. Launches whose own launch moment we cannot resolve are left out rather than
  counted. **An echo shows repeated behaviour. It does not show that the wallets are connected.**
- **We could not check.** Missing data is never dressed up as a finding. The page separates
  "history unavailable", "no price data", "too little history" and "checked, nothing found".

## Which Nansen endpoints do what

| Endpoint | What it gives Déjà View |
|---|---|
| `/api/v1/tgm/token-information` | Deployment time and symbol for a launch, and for every earlier launch we verify |
| `/api/v1/tgm/dex-trades` | The launch moment, the first hour's buyers, and the prices behind every move we quote |
| `/api/v1/profiler/dex-trades` | Each buyer's trades in the 30 days before the launch, which is where the record comes from |
| `/api/v1/tgm/token-ohlcv` | The price line across the first hour |
| `/api/v1/token-screener` | Finding launches worth scanning |

Usage receipt: **22,416 successful requests and 22,660 credits charged** between 14 and 16 September
2026, from the local call ledger. Reproduce it with `.venv/bin/python tools/api_usage.py`.

## Checking our claims

```bash
.venv/bin/python tools/test_claims.py       # offline, no API calls
```

These checks guard the sentences the page says out loud: an echo must be a verified early entry, a
wallet we could not read must never appear as a new face, wallets and buy times must stay paired,
and a cached scan must give the same answer next week as it did today.

Two more tools, both offline apart from one call each in `backfill_prices.py`:

```bash
.venv/bin/python tools/recompute_replays.py   # rebuild saved replays after a rule change
.venv/bin/python tools/build_art.py           # rebuild web/art/ from the source art
```

## What we do not claim

Not smart money. Not proven. Not profitable. Not coordinated. Not insider. No predictions, no
probabilities. A move we quote is what a coin offered within an hour of a buy, capped at 10×, and it
is never what anyone actually made.

The research behind Launch Reflex is written up honestly, including the first hypothesis that
failed, in [`docs/`](docs/). The frozen retest is `docs/D3_RETEST_PLAN.md`; its result is a modest
persistence effect measured on 37 actors, not evidence that tonight's VIP will make money.

## Credits and licence

- Code: **MIT**, see [LICENSE](LICENSE). Use it, change it, ship it; just keep the copyright line.
- Built by [MicroQuack](https://github.com/MicroQuack).
- Art generated with Codex and Grok Imagine, cut out and compressed by `tools/build_art.py`.
- Music: **"Neon Synthwave Vibe" by Lumen Sound**, from [Pixabay](https://pixabay.com/music/synthwave-neon-synthwave-vibe-554114/),
  used under the Pixabay Content Licence. Certificate: [`docs/licences/`](docs/licences/).
- Data from the **Nansen API**.
