"""Process raw avatar frames → transparent PNGs for Atrium.

Input:  model/animations/{1,2,3,4}.jpg   (RGB, baked background)
Output: packages/atrium/public/avatar/sonya_{closed,half,open,wide}.png
        (RGBA, background removed, auto-cropped, consistent canvas)

Steps per frame:
  1. rembg → cut subject with alpha matte (handles silver-hair-on-light-bg).
  2. Compute a SINGLE shared bbox across all frames (so head doesn't shift
     between frames — critical for talk animation), then crop all to it.
  3. Save PNG with transparency.

Run from repo root:
  .venv-imgtools\\Scripts\\python packages\\atrium\\tools\\process_avatar.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from rembg import remove, new_session

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "model" / "animations"
OUT = ROOT / "packages" / "atrium" / "public" / "avatar"
OUT.mkdir(parents=True, exist_ok=True)

FRAMES = [
    ("1.jpg", "sonya_closed.png"),
    ("2.jpg", "sonya_half.png"),
    ("3.jpg", "sonya_open.png"),
    ("4.jpg", "sonya_wide.png"),
]

# Use a model tuned for people/anime portraits.
session = new_session("isnet-anime")


def cut(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    out = remove(img, session=session, post_process_mask=True)
    return out


def main() -> None:
    cuts = []
    for src_name, _ in FRAMES:
        p = SRC / src_name
        if not p.exists():
            print(f"!! missing {p}")
            continue
        c = cut(p)
        cuts.append(c)
        print(f"cut {src_name}: {c.size}")

    if not cuts:
        print("no frames processed")
        return

    # Shared bbox across all frames so the head stays fixed between frames.
    union = None
    for c in cuts:
        bb = c.getbbox()  # bbox of non-transparent content
        if bb is None:
            continue
        if union is None:
            union = list(bb)
        else:
            union[0] = min(union[0], bb[0])
            union[1] = min(union[1], bb[1])
            union[2] = max(union[2], bb[2])
            union[3] = max(union[3], bb[3])

    # Pad a little so edges aren't tight.
    if union:
        w, h = cuts[0].size
        pad = 12
        union[0] = max(0, union[0] - pad)
        union[1] = max(0, union[1] - pad)
        union[2] = min(w, union[2] + pad)
        union[3] = min(h, union[3] + pad)
        print("shared bbox:", union)

    for (src_name, out_name), c in zip(FRAMES, cuts):
        if union:
            c = c.crop(tuple(union))
        dst = OUT / out_name
        c.save(dst)
        print(f"wrote {out_name}: {c.size}")


if __name__ == "__main__":
    main()
