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

## 1. New club background, boards filled in

**Round 2 attempt (16 Sept) cannot be used:** the queue contains Pepe the Frog and a Doge shiba. Both are existing
meme characters, Pepe is owned by a real artist, and the queue fills the space the buyer cards sit in.

- **File:** `club-bg-v2.png`, landscape 16:9, at least 1600 px wide.
- **The venue must be empty.** The page draws every character. No frog, no dog, no crowd, no bouncer, nobody at all.
- **Keep the bottom third plain** (carpet, ropes, wet pavement). The buyer cards cover it.
- **Keep the right side clear** below the sign. Our own bouncer stands there.
- **Painted words are fine** if they never change per launch. Keep them to the venue name and club signs.

Prompt:

> Cinematic neon nightlife illustration, semi-realistic stylised 3D, wide 16:9. Night street outside an exclusive
> nightclub, seen from across the pavement. A glowing doorway at centre-right with violet light spilling out and a disco
> ball inside. A red carpet runs from the door toward the bottom-left, with gold stanchions and red velvet ropes. Palm
> trees, wet pavement reflections, magenta and cyan neon tubes. Above the door, a black marquee lit in neon that reads
> exactly "DÉJÀ VIEW", and under it in smaller letters "SAME FACES. DIFFERENT LAUNCH." To the right of the door, a
> framed black guest-list board with the header "GUEST LIST" in gold and four rows, each a small light and one word: a
> gold light "VIP", a cyan light "STRONG", a pale grey light "KNOWN", a dashed grey ring "NEW FACE".
> **The venue is completely empty: no people, no animals, no characters, no frog, no dog, no bouncer, no crowd, no
> silhouettes, nobody in the queue.** No other writing, no coin names, no prices. The bottom third of the image is plain
> red carpet and wet pavement. Dark purple night, moody, high detail.

## 2. Living background loop (Grok Imagine, image to video)

- **Do this after image 1 exists and is empty of people.** Start from `club-bg-v2.png`.
- **File:** `club-loop.mp4`, 6 seconds is plenty. Claude strips the sound and compresses it.

Prompt:

> Animate this still image. The camera does not move. **Do not add any people, animals, or characters.** Do not change
> any writing. Light rain falls on the wet pavement and the reflections ripple. The magenta and cyan neon tubes flicker
> gently. Light from the disco ball turns slowly inside the doorway. Palm leaves and velvet ropes sway slightly in a
> night breeze. The marquee glow pulses softly. Seamless loop, cinematic.

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
