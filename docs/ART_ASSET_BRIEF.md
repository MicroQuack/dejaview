# Déjà View art assets: brief for an image generator

**Why this exists:** the working page draws its scene and characters in code. The mockup looked better because an
image model painted it. The plan is to split the work: an image model paints the art, and the page places that art
using real launch data. The same wallet always gets the same character.

**Who makes these:** Codex (it has image generation) or Grok Imagine. Save the files into `web/art/raw/`.
Claude then cuts out backgrounds, slices sheets, compresses, and wires them in.

## Hard rules for every image

- **No text, letters, numbers, or logos anywhere.** The page adds all words, so they can be honest and change per launch.
- **No existing characters or memes.** No Pepe, no Wojak, no Doge, no brand mascots. Every character must be original.
- **One consistent style across all images:** cinematic neon nightlife illustration, semi-realistic stylised 3D, dark
  purple night, magenta and violet neon, cyan accents, soft rim light.
- **Characters on a flat, pure green background (#00FF00),** with no shadow on the background and no green on the character.

## 1. Club background

- **File:** `club-bg.png`, landscape, at least 1920 × 1080.
- **Scene:** a night street outside an exclusive club. A glowing doorway at the centre-right, with violet light spilling out.
  A red carpet runs from the door toward the bottom-left. Gold stanchions with red velvet ropes line the carpet. Palm trees and
  a brick wall with neon tubes.
- **Leave empty:** the carpet and the queue area on the left (the page places characters there), a blank dark sign board
  above the door, and a blank board to the right of the door.
- **No people in the image.**

Prompt:

> Cinematic neon nightlife illustration, semi-realistic stylised 3D. Night street outside an exclusive nightclub. A glowing
> doorway at centre-right with violet light spilling out, a red carpet running from the door toward the bottom-left, gold
> stanchions with red velvet ropes along the carpet, palm trees, brick wall with magenta and cyan neon tubes. A blank dark
> sign board above the door and a blank board beside it. No people, no text, no letters, no logos. Dark purple night,
> moody, high detail, wide 16:9.

## 2. Party guests: 3 character sheets

- **Files:** `guests-sheet-1.png`, `guests-sheet-2.png`, `guests-sheet-3.png`.
- **Layout:** each sheet is a grid of 4 columns × 2 rows = 8 characters, evenly spaced, each fully inside its cell, not touching.
- **Pose:** waist-up, three-quarter view, facing right (toward the door), same scale and same head height in every cell.
- **Background:** flat pure green (#00FF00).

Prompt (change the variety line per sheet):

> Character sheet, 4 columns by 2 rows, 8 different original characters, evenly spaced on a flat pure green #00FF00
> background. Cinematic neon nightlife illustration, semi-realistic stylised 3D, consistent style and lighting across all
> 8. Each character waist-up, three-quarter view facing right, same scale, same head height, fully inside its cell.
> Crypto party guests in streetwear: hoodies, bomber jackets, chains, sunglasses, visors, caps, masks. Magenta and cyan
> rim light. Original characters only, no memes, no famous characters. No text, no letters, no logos.

Variety lines:

- **Sheet 1:** humans of different ages and styles, and two with face masks.
- **Sheet 2:** original anthropomorphic animals (fox, owl, bear, cat, raccoon, lizard, rabbit, shark), each in streetwear.
- **Sheet 3:** stranger guests: a small robot, an alien, a hooded figure with glowing eyes, a skeleton in a suit,
  a masked luchador, a plant creature, a cyborg, a ghost in sunglasses.

## 3. The bouncer

- **File:** `bouncer.png`, portrait, at least 768 × 1024.
- **Prompt:**

> Cinematic neon nightlife illustration, semi-realistic stylised 3D. An original large bouncer character in a black suit and
> sunglasses, arms crossed, three-quarter view facing left, waist-up, on a flat pure green #00FF00 background. Magenta and
> cyan rim light. Original character, no memes. No text, no letters, no logos.

## After the images exist (Claude's part)

1. Install Pillow in the virtual environment, remove the green background, and slice each sheet into 8 files.
2. Export as WebP, about 300 px wide for guests, and check the total stays under 5 MB.
3. Assign a guest by `hash(wallet) % 24`, so the same wallet always gets the same character.
4. Keep the code-drawn tier ring, crown, and labels on top of the art, and crop head circles for the timeline markers.
5. Keep the code-drawn scene as a fallback when an image is missing.
