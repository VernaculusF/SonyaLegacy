"""Generate Atrium placeholder icon set for Tauri bundling.

Cold silver-minimalism palette (her aesthetic): dark bg + eye-blue 'A' glyph.
Produces the files tauri.conf.json references: 32x32.png, 128x128.png,
128x128@2x.png, icon.ico, icon.png (+ Square*/StoreLogo for completeness).

Run: python gen_icons.py   (from src-tauri/)
Replace with a real icon later — this is a non-blocking placeholder.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "icons"
OUT.mkdir(parents=True, exist_ok=True)

BG = (14, 15, 18, 255)        # near-black (--bg)
RING = (138, 163, 184, 255)   # eye-blue (--acc-her-eyes)
GLYPH = (201, 205, 212, 255)  # silver (--acc-her)


def _font(size: int):
    for name in ("seguisb.ttf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)
    # subtle rounded border ring
    pad = max(1, size // 16)
    d.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=size // 6,
        outline=RING,
        width=max(1, size // 32),
    )
    # centered 'A' glyph (Atrium)
    f = _font(int(size * 0.6))
    text = "A"
    try:
        bbox = d.textbbox((0, 0), text, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(
            ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
            text, font=f, fill=GLYPH,
        )
    except Exception:
        pass
    return img


def main() -> None:
    sizes = {
        "32x32.png": 32,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "icon.png": 512,
        "Square30x30Logo.png": 30,
        "Square44x44Logo.png": 44,
        "Square71x71Logo.png": 71,
        "Square89x89Logo.png": 89,
        "Square107x107Logo.png": 107,
        "Square142x142Logo.png": 142,
        "Square150x150Logo.png": 150,
        "Square284x284Logo.png": 284,
        "Square310x310Logo.png": 310,
        "StoreLogo.png": 50,
    }
    for name, sz in sizes.items():
        make(sz).save(OUT / name)
        print("wrote", name, sz)

    # Windows .ico (multi-resolution)
    ico = make(256)
    ico.save(OUT / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote icon.ico")

    # macOS .icns — Pillow can write it from a square image
    try:
        make(1024).save(OUT / "icon.icns")
        print("wrote icon.icns")
    except Exception as e:
        print("icns skipped:", e)


if __name__ == "__main__":
    main()
