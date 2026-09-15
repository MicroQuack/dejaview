# Visual polish review: Déjà View launch party page

You are a senior product designer and motion designer reviewing a hackathon demo page. Read only. Do not run code.

## Look at these first

Screenshots in `spike_out/review-shots/` (open each image):

1. `1-mid-replay.png`: the replay halfway through. Four buyers have arrived, four are "Not here yet".
2. `2-replay-end-top.png`: the end of the replay. Three buyers glow violet because they share an "echo".
3. `3-replay-end-full.png`: the whole page at the end, including the panels below.
4. `4-home-idle.png`: the page before anyone pastes a coin.
5. `5-all-art.png`: all the generated art: club background, bouncer, 24 guest portraits on green screen.

The page code is `web/index.html` if you need detail. The art pipeline is in `docs/ART_ASSET_BRIEF.md`.

## What the product is

Déjà View, entry for the Nansen API buildathon. Submission is due 2026-09-26. Judges watch a **silent 30 to 45 second demo video** and may open the live page.

Paste a pump.fun token. The page replays the launch's first hour as a club night. The 8 biggest buyers arrive in the order they bought. Each wallet always gets the same generated character. When a buyer arrives, the page checks their record on earlier launches and labels them: VIP (top 5%, gold), Strong (cyan), Known (grey), New face. The bouncer comments on each arrival. **Echoes** are earlier launches that two or more of today's buyers were also early on.

## Rules the design must keep

- No existing meme or famous characters. All characters original.
- Never imply: smart money, proven, profitable, coordinated, insider, predictions, probabilities. Echoes show repeated behaviour, not connected wallets.
- Words that change per launch (coin name, scores) must come from the page, not be painted into an image.
- It is a plain HTML page with no build step. Images, CSS, and small JavaScript are fine. Video files (WebM or MP4) are fine if small.
- The owner can generate new art with Codex image generation and Grok Imagine (images and short image-to-video clips).

## What the owner wants

"It looks good, it needs professional polish." Specifically they asked about:

- The blank sign board above the door and the blank board on the right look weird. They plan to have the background redone with the boards filled.
- Music or sound.
- More animation in places.
- **Guests visibly turning up in the queue.** Compositing the waist-up portraits into the street scene looked like a cheap collage, so the guests are now portrait cards along the bottom. Could Grok Imagine clips help, for example a short arrival or idle loop per character, or a living background loop?

## What to give back

Plain words, short, no jargon. Rank everything by impact on a silent 40-second demo.

1. **Top 5 fixes** that would make it look most professional, each with one line on why and a rough size (small, medium, large).
2. **Arrival animation:** the best way to make guests feel like they are turning up, given waist-up portraits. Say what is code and what is generated video.
3. **Grok Imagine and Codex prompts:** write the exact prompts for any image or video you recommend, including the new background with the boards filled in. For the boards, suggest what they should say or show that stays true for every launch (for example the brand name "Déjà View" on the sign).
4. **Sound:** whether to add it, what kind, and how to keep it tasteful (muted by default is expected because browsers block autoplay).
5. **The timeline strip under the scene:** is violet glow on echo buyers clear? Anything better?
6. **Anything that looks amateur** that we have not mentioned.
7. **What to cut.**
