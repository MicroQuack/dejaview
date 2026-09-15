# Déjà View art, round 2: prompts to paste

**Why:** the page now uses the painted club as a backdrop, with buyers as portrait cards along the bottom and the
bouncer on the right. Grok's visual review (`docs/reviews/2026-09-15-grok-visual.md`) found two art gaps:
blank boards and a still scene. **No new characters:** the page uses all 24 guests and the current bouncer.

**Save every file into `web/art/raw/`** with the file name given. Claude compresses them and wires them in.

## Rules for every image and clip

- **Original characters only.** No memes, no famous characters, and no resemblance to a real celebrity.
- **No coin names, dollar signs, scores, or dates.** Those change per launch, so the page adds them.
- **Same style as the current art:** cinematic neon nightlife illustration, semi-realistic stylised 3D, dark purple
  night, magenta and violet neon, cyan accents.

## 1. New club background, boards filled in (Codex)

- **File:** `club-bg-v2.png`, landscape 16:9, at least 1920 × 1080.
- **Keep the layout of the current `club-bg.png`**, so the page still fits: door centre-right, board to its right,
  palms and skyline on the left.
- **Keep the bottom third plain** (carpet and wet pavement). The buyer cards cover it.
- **Keep the right edge fairly plain below the board.** The bouncer stands there.
- **Check the spelling** of both boards before saving. If the letters come out wrong, try again, or leave the boards
  lit but blank and tell Claude.

Prompt:

> Cinematic neon nightlife illustration, semi-realistic stylised 3D, wide 16:9. Night street outside an exclusive
> nightclub. A glowing doorway at centre-right with violet light spilling out and a disco ball visible inside. A red
> carpet runs from the door toward the bottom-left, with gold stanchions and red velvet ropes. Palm trees, a brick wall
> with magenta and cyan neon tubes, wet pavement reflections, a city skyline and water in the distance on the left.
> Above the door, a black marquee sign lit with magenta neon capital letters that read exactly "DÉJÀ VIEW".
> To the right of the door, a framed black guest-list board. Its header reads exactly "GUEST LIST" in gold. Below it,
> four rows, each with a small light and one word: a gold light and "VIP", a cyan light and "STRONG", a pale grey light
> and "KNOWN", a dashed grey ring and "NEW FACE". No other writing anywhere. No people, no cars. The bottom third of the
> image is plain red carpet and wet pavement. Dark purple night, moody, high detail.

## 2. Living background loop (Grok Imagine, image to video)

- **Do this after image 1 exists.** Start from `club-bg-v2.png`.
- **File:** `club-loop.mp4`, 6 seconds, same framing as the still.

Prompt:

> Animate this still image. The camera does not move. Do not add objects or people, and do not change any writing.
> Light rain falls on the wet pavement and the reflections ripple. The magenta and cyan neon tubes flicker gently. Light
> from the disco ball turns slowly inside the doorway. Palm leaves and velvet ropes sway slightly in a night breeze. The
> marquee glow pulses softly. Seamless loop, cinematic.

## 3. Optional: bouncer idle loop (Grok Imagine, image to video)

- **Only after 1 and 2 are done.** Start from the current `bouncer.png`.
- **File:** `bouncer-loop.mp4`, 3 seconds.

Prompt:

> Animate this character. The camera does not move. Keep the flat pure green #00FF00 background unchanged. He breathes
> slowly, glances toward the left, then back. Arms stay crossed. No smile, no speech, no extra people. Seamless loop.

## Not needed

- **Arrival clips for each guest.** The page now brings each guest in one at a time, so the portraits stay as they are.
- **New guests or a new bouncer.**

## After the files exist (Claude's part)

1. Rebuild `web/art/` with `tools/build_art.py`: new background and compressed loops.
2. Play `club-loop` behind the cards, with the still image as the fallback.
3. Remove the green from `bouncer-loop` into a transparent video, and fall back to the still bouncer.
4. Keep the total art under about 8 MB.
