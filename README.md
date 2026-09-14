# Déjà View

*We've seen this trade before.*

Déjà View shows who is buying a new Solana token launch, and how those buyers' earlier launch
buys played out. It scores each meaningful first-hour buyer with **Launch Reflex**: how often the
wallet's past launch buys went on to offer a strong first-hour opportunity, ranked against other
launch buyers.

Built for the Nansen Meridian Buildathon. **Powered by Nansen API.**

## The 30-second version

1. Paste a Solana token address.
2. Déjà View finds the token's launch moment: the first time its DEX volume reaches $5,000.
3. It picks the largest buyers from the first hour after that moment.
4. For each buyer, it looks back 30 days, strictly before the launch moment, and finds the other
   launches that wallet bought within 6 hours.
5. For each of those earlier launches, it measures the best price reached within an hour of the
   wallet's entry.
6. It ranks the wallet against a reference set of launch buyers and explains the score.

## Demo

Recording: to be added before submission.

## Why Launch Reflex is not Smart Money

Smart Money labels say a wallet has done well in general. Launch Reflex asks a narrower
question: when this wallet buys a brand-new token in its first hours, does that token tend to go on
to offer a real opportunity? A wallet can be a strong long-term holder and a poor launch picker,
or the other way around.

## Does it work? The evidence

Before any product code, a spike tested whether Launch Reflex measures something real. The full log,
including the tests that failed, is in [spike_results.md](spike_results.md).

- **The first design failed.** Scoring wallets on 24-hour token returns could not tell wallets apart.
  The spread in scores matched random chance.
- **The measure changed for a stated reason.** Launch buyers usually hold for minutes, so the outcome
  moved to the first hour.
- **A wider retest passed rules frozen before any data was fetched**
  ([docs/D3_RETEST_PLAN.md](docs/D3_RETEST_PLAN.md)). It covered 37 buyers across 8 randomly sampled
  launches, including launches that died. A wallet's score on its older launches predicted its score on
  newer launches (rank correlation 0.42; stronger than 99.6% of random shuffles). The result held after
  removing each launch in turn, after dropping each wallet's best trade, after adjusting for market week,
  and after adjusting for entry speed.
- **The effect is moderate.** A high Launch Reflex improves the odds. It does not guarantee anything.

## How Launch Reflex is calculated

| Step | Rule |
|---|---|
| Launch moment (T0) | First time cumulative DEX volume after deployment reaches $5,000, counting each swap once |
| Meaningful buyers | Buys of at least $500 from deployment to T0 + 1 hour, ranked by total size; pools, routers, and exchanges excluded; top 8 |
| Prior launch entry | The wallet's first buy of another token within 6 hours of that token's T0, or of its deployment if it never reached $5,000 (a failed launch) |
| Entry price | Median market price in the 2 minutes around the wallet's buy |
| First-hour opportunity | Log of the 5th-highest trade price in the hour after entry, divided by the entry price, capped at ±ln 10 |
| Score | Mean first-hour opportunity over up to 16 recent prior launch entries, shrunk toward the reference average |
| Launch Reflex | Percentile of that score among the 37 reference buyers from the retest |
| Confidence | High: 16 entries. Medium: 8 to 15. Low: 3 to 7. Fewer than 3: not scoreable |

**Point-in-time trade cutoff:** Déjà View never uses wallet trades that occur after the launch being
evaluated. Historical enrichment supplied by Nansen may subsequently be restated or corrected.

Launch Reflex is relative. A score of 92 means the wallet ranks above 92% of reference launch buyers.
It is not a 92% win rate.

## Nansen endpoints

| Endpoint | Used for | Credits a call |
|---|---|---|
| `/api/v1/tgm/token-information` | Deployment time | 1 |
| `/api/v1/tgm/dex-trades` | Launch moment, first-hour buyers, market prices | 1 |
| `/api/v1/profiler/dex-trades` | Wallet history before the launch moment | 1 |
| `/api/v1/token-screener` | Finding recent launches during the spike | 1 |
| `/api/v1beta1/token-screener/historical` | Sampling past launches without survivorship for the retest | 5 |

## Performance and caching

- A cold scan takes about 1 minute and about 300 API calls. A repeat scan takes about 2 seconds.
- Caches store enrichment, never scores: launch moments per token, market prices per entry, and wallet
  history per wallet. Scores are recalculated at each launch's own cutoff.
- Every request is logged to `spike_out/calls.jsonl`, the record of API usage for the competition.

## Limitations

- **Pump.fun launches only.** The launch-moment and price methods were validated there.
- **Opportunity, not profit.** Nansen trade data does not show whether the wallet sold near the peak.
- **Moderate effect.** Treat Launch Reflex as evidence, not a signal to copy.
- **Shallow history for very active wallets.** Each history window returns up to 1,000 trades, which covers
  only a few days for high-frequency wallets.
- **Small reference set.** Percentiles come from 37 reference buyers, so they move in steps of about 3.
- **Retries can change a score.** If a price request fails, that entry is left out. A later scan fills it
  in, which can move the score.

## Set up in under 10 minutes

You need Python 3.10 or later and a Nansen API key from [app.nansen.ai/api](https://app.nansen.ai/api).

1. Clone the repository and change into it.
2. Create a virtual environment and install the dependency:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env`, then add your key after `NANSEN_API_KEY=`.
4. Start the app:

   ```bash
   .venv/bin/python app.py
   ```

5. Open <http://localhost:8420> and paste a Solana token address, or click a replay example.

To use another port, set `DEJAVIEW_PORT`. To scan from the terminal, run
`.venv/bin/python reflex.py <token address>`.

A cold scan uses about 300 credits.

## Architecture

| File | Role |
|---|---|
| `app.py` | Local web server; streams scan progress to the page |
| `web/index.html` | The scan page |
| `reflex.py` | Scan orchestration and Launch Reflex scoring |
| `launch_data.py` | Launch moment, wallet first buys, market prices, caches |
| `nansen_client.py` | Nansen API client with retries and the call ledger |
| `data/reflex_reference.json` | Reference scores from the retest; derived numbers only |
| `spike_runner.py`, `d3.py` | Spike and retest code |
| `tools/build_reference.py` | Rebuilds the reference from local retest data |

## Attribution and data

Powered by Nansen API. The repository contains derived metrics only. Raw Nansen responses, wallet
histories, and API keys stay local in `spike_out/` and `.env`, which git ignores.

## Future work

- Event fingerprint: entry speed, persistence, and concentration of a launch's buyers.
- Déjà View matching: the nearest past launches with a similar buyer pattern, showing winners and losers.
- A larger reference set of launch buyers.
