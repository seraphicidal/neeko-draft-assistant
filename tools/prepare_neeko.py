"""Turn the source Neeko illustrations into cut-out companion art.

The originals sit on flat white, pink or green backgrounds. The app composites
them onto dark navy, so each one is flood-filled from its corners, cut out,
trimmed to the subject and saved as a transparent PNG under a role name the UI
asks for by state.

Dev-time only, needs Pillow.

    python tools/prepare_neeko.py [source-folder]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "neeko"
DEFAULT_SOURCE = Path.home() / "OneDrive" / "Desktop" / "neeko"

MAGIC = (255, 0, 255)
MAX_SIDE = 620

# role, source file, flood tolerance, cut out at all, extra seed points.
# Seeds and the optional pre-crop box are fractions of the image, and only
# matter where the drawing sits on a coloured card inside a white frame: the
# corners never reach that inner background on their own.
SOURCES = [
    ("mood_idle", "450754c0b9a3d2ff51a0decb7e022586.jpg", 60, True, (), None),
    ("mood_happy", "d570685efab6296dcff412b7b3459aa9.jpg", 78, True, (), None),
    ("mood_alert", "image-1788485103629.webp", 60, True, (), None),
    # image-1788485107277.webp is deliberately left out: its green card has a
    # gradient, and a flood fill cannot separate it from Neeko's own green
    # without a real matting pass.
    ("mood_calm", "image-1788485110536.webp", 50, True, (), None),
    ("portrait", "image-1788485113681.webp", 0, False, (), None),
]


def cut_out(image: Image.Image, tolerance: int, extra_seeds=()) -> Image.Image:
    """Drop the flat background the illustration was drawn on."""
    rgb = image.convert("RGB")
    width, height = rgb.size

    seeds = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    seeds += [
        (min(width - 1, int(x * width)), min(height - 1, int(y * height)))
        for x, y in extra_seeds
    ]

    work = rgb.copy()
    for seed in seeds:
        ImageDraw.floodfill(work, seed, MAGIC, thresh=tolerance)

    # Anything the fill reached is background; everything else is Neeko.
    filled = ImageChops.difference(work, Image.new("RGB", rgb.size, MAGIC)).convert("L")
    alpha = filled.point(lambda value: 0 if value < 12 else 255)
    # A touch of blur softens the stair-stepping the threshold leaves behind.
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8)).point(
        lambda value: 0 if value < 90 else min(255, int(value * 1.35))
    )

    cut = rgb.convert("RGBA")
    cut.putalpha(alpha)
    return cut


def trim(image: Image.Image) -> Image.Image:
    box = image.getchannel("A").getbbox()
    return image.crop(box) if box else image


def fit(image: Image.Image, longest: int = MAX_SIDE) -> Image.Image:
    if max(image.size) <= longest:
        return image
    scale = longest / max(image.size)
    return image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.LANCZOS,
    )


def main() -> int:
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source_dir.exists():
        print(f"source folder not found: {source_dir}")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    written = 0

    for role, filename, tolerance, has_background, seeds, pre_crop in SOURCES:
        source = source_dir / filename
        if not source.exists():
            print(f"  skipped {role}: {filename} is not there")
            continue

        image = Image.open(source)
        if pre_crop:
            left, top, right, bottom = pre_crop
            image = image.crop(
                (
                    int(left * image.width),
                    int(top * image.height),
                    int(right * image.width),
                    int(bottom * image.height),
                )
            )
        prepared = (
            trim(cut_out(image, tolerance, seeds))
            if has_background
            else image.convert("RGBA")
        )
        prepared = fit(prepared)

        destination = OUT / f"{role}.png"
        prepared.save(destination, optimize=True)
        coverage = prepared.getchannel("A").getextrema()[1]
        print(
            f"  {role:14} {prepared.size[0]:>4}x{prepared.size[1]:<4} "
            f"{destination.stat().st_size:>8,} bytes"
            + ("" if coverage else "   WARNING: fully transparent")
        )
        written += 1

    print(f"\nwrote {written} files to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
