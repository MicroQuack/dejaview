#!/usr/bin/env python3
"""Build web/art/ from the generated images in web/art/raw/.

Removes the green screen, slices the guest sheets into single characters, crops a head
square for avatars, and writes WebP files plus web/art/manifest.json for the page.
Needs Pillow and numpy (dev only): .venv/bin/pip install pillow numpy
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "web" / "art" / "raw"
OUT = ROOT / "web" / "art"
GUEST_W, HEAD_PX, BG_W = 300, 128, 1672
SKIP = {"3-6"}  # sheet 3, cell 6: the plant creature looks too close to a famous film character

# Per-guest head nudges, as fractions of the sprite: (dx, dy, radius scale). Tuned by eye.
HEAD_FIX = {"2-6": (.05, .02, 1), "2-7": (.03, .09, 1)}


def key_out(rgb):
    """Green screen to alpha, with the green spill pulled off the edges."""
    a = rgb.astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    greenness = g - np.maximum(r, b)
    alpha = np.clip(1 - (greenness - 40) / 90, 0, 1)
    a[..., 1] = np.minimum(g, np.maximum(r, b))  # despill
    return np.dstack([a, alpha * 255]).astype(np.uint8)


def cut(mask, axis, near, spread):
    """Index of the emptiest line close to `near`."""
    counts = mask.sum(axis=axis)
    lo, hi = max(0, near - spread), min(len(counts), near + spread)
    return lo + int(np.argmin(counts[lo:hi]))


def trim(rgba):
    ys, xs = np.nonzero(rgba[..., 3] > 24)
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def head_box(rgba, fix):
    """Guess the head circle: sprites are waist-up with the head in the top third."""
    h, w = rgba.shape[:2]
    band = rgba[int(h * .08):int(h * .32), :, 3].astype(np.float32)
    cx = float((band.sum(axis=0) * np.arange(w)).sum() / band.sum()) / w
    dx, dy, rs = fix
    # x and r are fractions of the width, y of the height.
    return {"x": round(cx + dx, 3), "y": round(.2 + dy, 3), "r": round(.19 * h / w * rs, 3)}


def save(rgba, path, width, quality=82):
    im = Image.fromarray(rgba)
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(path, "WEBP", quality=quality, method=6)
    return im.size


def main():
    (OUT / "guests").mkdir(exist_ok=True)
    (OUT / "heads").mkdir(exist_ok=True)
    manifest = {"guests": []}

    bg = Image.open(RAW / "club-bg.png").convert("RGB")
    bg = bg.resize((BG_W, round(bg.height * BG_W / bg.width)), Image.LANCZOS)
    bg.save(OUT / "club-bg.webp", "WEBP", quality=80, method=6)
    manifest["bg"] = {"src": "art/club-bg.webp", "w": bg.width, "h": bg.height}

    bouncer = trim(key_out(np.asarray(Image.open(RAW / "bouncer.png").convert("RGB"))))
    w, h = save(bouncer, OUT / "bouncer.webp", 520)
    manifest["bouncer"] = {"src": "art/bouncer.webp", "w": w, "h": h}

    for sheet in (1, 2, 3):
        rgba = key_out(np.asarray(Image.open(RAW / f"guests-sheet-{sheet}.png").convert("RGB")))
        mask = rgba[..., 3] > 128
        H, W = mask.shape
        mid = cut(mask, 1, H // 2, H // 8)
        for row, (top, bottom) in enumerate([(0, mid), (mid, H)]):
            part = mask[top:bottom]
            xs = [0] + [cut(part, 0, W * k // 4, W // 12) for k in (1, 2, 3)] + [W]
            for col in range(4):
                cell = f"{sheet}-{row * 4 + col + 1}"
                if cell in SKIP:
                    continue
                sprite = trim(rgba[top:bottom, xs[col]:xs[col + 1]])
                name = f"g{len(manifest['guests']):02d}"
                sw, sh = save(sprite, OUT / "guests" / f"{name}.webp", GUEST_W)
                head = head_box(sprite, HEAD_FIX.get(cell, (0, 0, 1)))
                # Square head crop for the round avatars.
                s = sprite.shape[1]
                side = round(head["r"] * 2.7 * s)
                x0, y0 = round(head["x"] * s - side / 2), round(head["y"] * sprite.shape[0] - side / 2)
                square = np.zeros((side, side, 4), np.uint8)
                ys0, xs0 = max(0, y0), max(0, x0)
                ys1, xs1 = min(sprite.shape[0], y0 + side), min(s, x0 + side)
                square[ys0 - y0:ys1 - y0, xs0 - x0:xs1 - x0] = sprite[ys0:ys1, xs0:xs1]
                save(square, OUT / "heads" / f"{name}.webp", HEAD_PX)
                manifest["guests"].append({"id": name, "cell": cell, "w": sw, "h": sh, "head": head})

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    total = sum(p.stat().st_size for p in OUT.rglob("*.webp"))
    print(f"{len(manifest['guests'])} guests, {total / 1e6:.2f} MB of WebP")


if __name__ == "__main__":
    main()
