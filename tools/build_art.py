#!/usr/bin/env python3
"""Build web/art/ from the generated images in web/art/raw/.

Removes the green screen, slices the guest sheets into single characters, crops a head
square for avatars, turns the generated clips into seamless loops, and writes the files
plus web/art/manifest.json for the page.
Needs Pillow, numpy, and ffmpeg (dev only): .venv/bin/pip install pillow numpy
"""

import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "web" / "art" / "raw"
OUT = ROOT / "web" / "art"
GUEST_W, HEAD_PX, BG_W = 300, 128, 1672
LOOP_S = 7                      # club loop: seconds taken from the clip, then played forward and backward
BOUNCER_S = 6                   # bouncer loop: played forward then backward, so it never jumps
BOUNCER_CROP = (.14, 0, .92, 1)  # left, top, right, bottom of the frame he moves inside
SKIP = set()  # sheet-cell ids to leave out, for example "3-6"

# Per-guest head nudges, as fractions of the sprite: (dx, dy, radius scale). Tuned by eye.
HEAD_FIX = {"2-6": (.05, .02, 1), "2-7": (.03, .09, 1)}


def ffmpeg(args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def club_loop(src, dst):
    """Play the clip forward then backward, so the loop never jumps. A cross-fade ghosts the painted signs."""
    chain = (f"[0:v]trim=0:{LOOP_S},setpts=PTS-STARTPTS,split=2[f][x];[x]reverse[rv];"
             f"[f][rv]concat=n=2:v=1:a=0[out]")
    ffmpeg(["-i", str(src), "-filter_complex", chain, "-map", "[out]", "-an",
            "-c:v", "libx264", "-crf", "30", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)])


def video_size(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0:s=x", str(path)], capture_output=True, text=True, check=True).stdout.strip()
    w, h = out.split("\n")[0].split("x")
    return int(w), int(h)


def bouncer_loop(src, dst, poster):
    """Crop to the bouncer, drop the green, and play forward then backward. WebM keeps the transparency."""
    l, t, r, b = BOUNCER_CROP
    crop = f"crop=iw*{r - l}:ih*{b - t}:iw*{l}:ih*{t}"
    keyed = f"{crop},chromakey=0x00FF00:0.30:0.06,despill=type=green,scale=560:-2"
    ffmpeg(["-i", str(src), "-filter_complex",
            f"[0:v]trim=0:{BOUNCER_S},setpts=PTS-STARTPTS,{keyed},split=2[f][x];[x]reverse[rv];[f][rv]concat=n=2:v=1:a=0[out]",
            "-map", "[out]", "-an", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-crf", "36", "-b:v", "0", str(dst)])
    ffmpeg(["-ss", "1", "-i", str(src), "-frames:v", "1", "-vf", f"{crop},scale=560:-2", str(poster)])


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

    clip, still = RAW / "club-loop.mp4", RAW / "club-bg.png"
    if clip.exists():
        club_loop(clip, OUT / "club-loop.mp4")
        manifest["bg_video"] = {"src": "art/club-loop.mp4"}
        still = OUT / "club-still.png"  # the loop's own first frame, so the fallback matches the clip
        ffmpeg(["-i", str(OUT / "club-loop.mp4"), "-frames:v", "1", str(still)])

    bg = Image.open(still).convert("RGB")
    bg = bg.resize((min(BG_W, bg.width), round(bg.height * min(BG_W, bg.width) / bg.width)), Image.LANCZOS)
    bg.save(OUT / "club-bg.webp", "WEBP", quality=80, method=6)
    manifest["bg"] = {"src": "art/club-bg.webp", "w": bg.width, "h": bg.height}
    (OUT / "club-still.png").unlink(missing_ok=True)

    music = RAW / "club-music.mp3"
    if music.exists():
        ffmpeg(["-i", str(music), "-vn", "-ac", "2", "-b:a", "112k", str(OUT / "club-music.mp3")])
        manifest["music"] = {"src": "art/club-music.mp3"}

    bclip, poster = RAW / "bouncer-loop.mp4", OUT / "bouncer-still.png"
    if bclip.exists():
        bouncer_loop(bclip, OUT / "bouncer-loop.webm", poster)
        vw, vh = video_size(OUT / "bouncer-loop.webm")
        manifest["bouncer_video"] = {"src": "art/bouncer-loop.webm", "w": vw, "h": vh}
    bouncer_src = poster if poster.exists() else RAW / "bouncer.png"
    bouncer = trim(key_out(np.asarray(Image.open(bouncer_src).convert("RGB"))))
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
                # Loose enough that hair, ears, and hats stay inside the circle.
                side = round(head["r"] * 4.0 * s)
                x0, y0 = round(head["x"] * s - side / 2), round(head["y"] * sprite.shape[0] - side * .42)
                square = np.zeros((side, side, 4), np.uint8)
                ys0, xs0 = max(0, y0), max(0, x0)
                ys1, xs1 = min(sprite.shape[0], y0 + side), min(s, x0 + side)
                square[ys0 - y0:ys1 - y0, xs0 - x0:xs1 - x0] = sprite[ys0:ys1, xs0:xs1]
                save(square, OUT / "heads" / f"{name}.webp", HEAD_PX)
                manifest["guests"].append({"id": name, "cell": cell, "w": sw, "h": sh, "head": head})

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (OUT / "bouncer-still.png").unlink(missing_ok=True)
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"{len(manifest['guests'])} guests, {total / 1e6:.2f} MB in web/art/")


if __name__ == "__main__":
    main()
