**Video: reject as-is for small wording corrections; approve the underlying demonstration. Post: approve the main post; revise the reply to distinguish the public replay site from the local live scanner. Updated score: 92/100.**

The blocking issues are specific:

1. **“Each rated” and “open any buyer … behind their score” overstate coverage.** PAID has eight buyers but only five scores. Two could not be checked; one was checked and had no qualifying record.
2. **Disclose the cached histories in the live-scan caption.** Fresh buyers and prices support calling this a live scan, but “fresh Nansen data” alone can imply every history was fetched during that take.
3. **Complete the planned push and deployment before posting.** The submission links must expose the reviewed README and five saved replays. I could not independently verify the public destinations through the browser fetcher; those fetch failures do not establish that either destination is broken.

These require caption and release corrections, not a new concept or a complete rerecording.

**Rules and submission readiness**

The current [official campaign page](https://nansen.ai/campaigns/meridian-buildathon) confirms the four equally weighted criteria, the 1,000-call requirement, an X recording tagging `@nansen_ai`, and a submission containing email, X-post link and GitHub repository. It lists September 14–27. It does not specify that the posting account must match the repository owner, so the proposed author-account post is acceptable.

The usage requirement is comfortably met. Running the read-only usage script returned:

| Measure | Verified total |
|---|---:|
| Requests | 24,013 |
| Successful requests | 22,976 |
| Credits charged | 23,220 |

The brief’s “about 24,000 successful” confuses requests with successes. If quoting current usage, use **“22,976 successful Nansen API requests.”** This error is in the brief, not the proposed captions or post. The README’s older receipt is explicitly dated and need not be treated as a current total.

Posting and submitting the form remain outstanding, as expected for this review.

**Every caption checked**

The principal numerical sources are the [HYPED replay](/Users/sghmaster/Documents/Claude/Projects/Dejaview/data/replays/G2KDX81e31T6pZbkrJLPKAXqKcd8VoE3UEp83rRtpump.json), [PAID replay](/Users/sghmaster/Documents/Claude/Projects/Dejaview/data/replays/98kfF7rmsg1QDUEoCqNE7g7M1FdrTt92TEp2CLzypump.json), and [D3 results](/Users/sghmaster/Documents/Claude/Projects/Dejaview/spike_results.md:456).

| Time | Assessment | Exact replacement where needed |
|---|---|---|
| **0–9.5s** | **Pass.** The replay and repeat-buyer description accurately summarize the product. | Keep. |
| **9.5–24s** | **Change.** PAID’s September 15 date and eight buyers are supported. “Each rated” is false for three buyers. “Biggest” also refers to the app’s filtered selection. | **“$PAID, 15 Sept. Eight selected first-hour buyers arrive in order. We check their earlier launch records.”** |
| **24–35s** | **Pass.** PAID’s retained echoes include two buyers on BRAIN and three on EMBER. | Keep. |
| **35–40s** | **Change.** Unscored buyers do not have earlier launches “behind their score.” | **“Open a scored buyer to see the earlier launches behind their score.”** |
| **40–44s** | **Pass.** The wallet-link function constructs Nansen profiler links using each wallet’s address; the stills show the transition. | Keep. |
| **44–49.5s** | **Qualify.** HYPED launched the previous evening. Fresh trade and price requests are supported, but the histories were cached. | **“Fresh Nansen buyers and prices; wallet histories cached minutes earlier.”** |
| **49.5–66s** | **Substantively supported.** HYPED is September 16, with eight selected buyers and eight scoreable histories. Avoid implying an unfiltered ranking of every wallet. | **“$HYPED, 16 Sept. The scan selects eight large first-hour buyers and checks their earlier launch records.”** |
| **66–82s** | **Pass.** HYPED has verified shared earlier launches, including AQUA, PAID and PMARCA. | Keep. |
| **82–87s** | **Pass.** Six distinct HYPED buyers appear in the PAID echo, and its token address exactly matches the saved PAID replay. | Keep. |
| **87–92s** | **Numerically correct.** Score 100; 15 of 16 distinct measured launches reached 2×; 15/16 = 93.75%, rounded to 94%. | Prefer: **“Launch Reflex 100. Of 16 measured earlier launches, 15 offered a 2× move within an hour of the buy.”** |
| **92–98.07s** | **Supported, but make the research scope explicit.** D3 reports 37 qualifying actors from eight events. That is a retrospective scoring test, not a general reliability guarantee. | Prefer: **“Built for pump.fun. Launch Reflex was tested retrospectively across 37 buyers from 8 launches.”** |
| **Closing links and attribution** | Repository and site addresses match the README. Nansen attribution is justified by the implementation and ledger. Public release verification remains outstanding. | Keep after push/deploy verification. |

“Early” has a particular meaning here: entry within the project’s **six-hour launch window**, not necessarily the first hour. The claim checks confirm that retained echo members satisfy that rule. In particular, the six HYPED buyers need not all belong to PAID’s displayed eight first-hour buyers. The current echo captions do not claim that they do.

The buyer ranking also applies filters: qualifying trade sizes, excluded labels and a buy-count limit. HYPED reports 477 qualifying buyers and zero capped windows. Calling them “selected first-hour buyers” is more defensible than an unrestricted “the biggest buyers.”

**The live-scan honesty question**

**“Live scan” is fair. “Fresh Nansen data” is incomplete without the cache qualification.**

The call ledger records four successful `dex-trades` requests and one successful `token-ohlcv` request at approximately **08:43:30–08:43:32 UTC**, consistent with the recorded take described in the brief. This supports fresh buyer and chart data during the demonstration.

Reusing recently fetched histories is legitimate. The problem is only the possible implication that the rapid demonstration represents a fully uncached scan. The README already says a scan can take a few minutes.

For this video, the replacement caption above is sufficient; the existing page pill does not require rerecording once the caption supplies the missing qualification. For future interface wording, I would use:

> **Live scan · Nansen API**

One evidence limitation: the supplied HYPED JSON is timestamped **08:45:11**, with a save time of **08:45:13**, rather than the stated 08:43 recorded take. It corroborates the headline results but is not the exact take’s contemporaneous saved artifact. The 08:43 ledger independently supports the fresh-request claim.

The disclosed glitch removal, scroll fade and external-page loading cuts do not by themselves invalidate the demonstration. Do not describe the recording as unedited or as a cold-start timing benchmark.

**Post and reply**

The main post contains no banned claim:

- “Same faces, different places” is creative copy, not a factual overstatement. Its difference from the page tagline is harmless.
- The club-night description matches the visible experience.
- Checking earlier launch activity is supported.
- “Built on the `@nansen_ai` API” is accurate and supplies the required tag.
- The repository link is appropriate once the reviewed commits are public.

I would optionally tighten its middle paragraph to:

> Paste a pump.fun token and it replays the first hour as a club night. Eight selected buyers queue at the door while it checks their earlier launch records.

The reply’s six-buyer PAID claim is correct. **Keep “It shows repeated behaviour, not connected wallets.”** It states the crucial interpretation accurately.

The reply should clarify what visitors can actually try. The [README](/Users/sghmaster/Documents/Claude/Projects/Dejaview/README.md:39) describes the public static site as saved replays, with live scanning available locally using a Nansen key. Replace:

> Try it: dejaview-delta.vercel.app

with:

> **Try the saved replays on desktop: dejaview-delta.vercel.app**  
> **Run live scans locally with your own Nansen key; instructions in the repo.**

The music title and track ID match the retained certificate. The [Pixabay track page](https://pixabay.com/music/synthwave-neon-synthwave-vibe-554114/) identifies the uploader as `echoes_of_lumen`; the materials reviewed do not independently establish “Lumen Sound” as that uploader’s display name. For directly verifiable attribution, use:

> **Music: “Neon Synthwave Vibe” by echoes_of_lumen (Pixabay).**

No caption or proposed post makes a prohibited profit, insider, coordination, prediction or probability claim. The historical 94% figure is an observed frequency, not a forecast. Naming it separately from the percentile score reduces the chance of confusion.

**Presentation assessment**

The sequence communicates a complete story: recognize buyers, reveal shared history, inspect evidence, open Nansen, then repeat with freshly requested launch data. The six-buyer connection back to PAID is the strongest payoff. The bouncer and persistent characters make the concept memorable.

The remaining visual weaknesses are concrete:

- **24–30s:** the echo caption appears before the sampled stills show a populated echo panel. Align its start with the first visible echo.
- **70–82s:** the supplied stills show little new information while the replay advances. Shortening this stretch would improve pace.
- **25–34s and 64–84s:** lower cards extend below the visible area. The hero occupies substantial space while the evidence is small.
- **87–92s:** the current caption asks viewers to absorb a score, percentage, denominator and time horizon while reading a dense drawer. The count-based replacement is clearer.
- The final URL line is small for an X feed. A brief closing card with larger links would help.

These are polish opportunities, not reasons to rebuild the video.

**Updated judging score**

| Criterion | Score | Reason and what would raise it |
|---|---:|---|
| Data Integration | **24/25** | Nansen data drives selection, history, scores, echoes and evidence links. Explicit cache disclosure and an exact-take artifact would strengthen traceability. |
| Creativity & Originality | **24/25** | The club-door metaphor explains recognition effectively. Give the echo reveal more visual emphasis. |
| Functionality & Workability | **23/25** | The supplied sequence reaches completed results; all 34 offline claim checks pass. Verify the published build and a fresh-clone startup to strengthen the remaining evidence. |
| Documentation & Submission | **21/25** | Clear setup, endpoint mapping, definitions, limitations and a followable recording. Correct the captions, distinguish public replays from local scanning, and finish publication. |
| **Total** | **92/100** | Up from the brief’s previous 90, principally because the demonstration now makes the product understandable and shows the evidence path. |

This score assesses the supplied entry, not its likelihood of winning. I reviewed all 20 stills, verified the video’s 98.07-second duration and audio-stream presence, read the named data files and supporting code, and ran the offline checks successfully using the project virtual environment. I did not listen to the audio, verify continuous motion, time a fresh installation, or confirm the final public deployment.

**No files were edited.**