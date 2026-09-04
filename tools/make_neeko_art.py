"""Draw the decorative pieces of the Neeko theme.

Dev-time only, needs Pillow. Warm orange and light blue on a deep navy ground --
the app's own palette, with Neeko's magenta kept as a small accent.

    python tools/make_neeko_art.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "assets"
NEEKO = ASSETS / "neeko"

NAVY = (10, 16, 28)
NAVY_UP = (18, 28, 48)
ORANGE = (255, 138, 61)
ORANGE_DEEP = (242, 102, 28)
PEACH = (255, 214, 176)
SKY = (125, 211, 252)
SKY_BRIGHT = (56, 189, 248)
CYAN = (103, 232, 249)
CREAM = (255, 247, 236)
NEEKO_PINK = (232, 74, 168)
NEEKO_MINT = (79, 216, 200)


def _rotated_ellipse(draw, centre, radii, angle, fill):
    """An ellipse drawn as a polygon so it can be rotated."""
    cx, cy = centre
    rx, ry = radii
    points = []
    for step in range(72):
        theta = 2 * math.pi * step / 72
        x, y = rx * math.cos(theta), ry * math.sin(theta)
        points.append(
            (
                cx + x * math.cos(angle) - y * math.sin(angle),
                cy + x * math.sin(angle) + y * math.cos(angle),
            )
        )
    draw.polygon(points, fill=fill)


def flower(size=256, petal=ORANGE, centre=CREAM, petals=5) -> Image.Image:
    """Neeko's hair flower, recoloured: five orange petals and a cream star."""
    scale = 4
    canvas = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    middle = size * scale / 2
    radius = size * scale * 0.29

    for index in range(petals):
        angle = 2 * math.pi * index / petals - math.pi / 2
        _rotated_ellipse(
            draw,
            (middle + radius * math.cos(angle), middle + radius * math.sin(angle)),
            (size * scale * 0.20, size * scale * 0.135),
            angle,
            petal + (255,),
        )

    star = []
    for index in range(10):
        angle = math.pi * index / 5 - math.pi / 2
        length = size * scale * (0.115 if index % 2 == 0 else 0.05)
        star.append((middle + length * math.cos(angle), middle + length * math.sin(angle)))
    draw.polygon(star, fill=centre + (255,))

    return canvas.resize((size, size), Image.LANCZOS)


def leaf(width=128, height=256) -> Image.Image:
    """One of the crest spikes, orange fading into light blue."""
    scale = 4
    canvas = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.polygon(
        [
            (width * scale / 2, 0),
            (width * scale * 0.92, height * scale * 0.55),
            (width * scale / 2, height * scale),
            (width * scale * 0.08, height * scale * 0.55),
        ],
        fill=ORANGE + (255,),
    )
    # Light-blue half, so it reads like the two-tone spikes in the art.
    draw.polygon(
        [
            (width * scale / 2, 0),
            (width * scale * 0.92, height * scale * 0.55),
            (width * scale / 2, height * scale),
        ],
        fill=SKY + (255,),
    )
    return canvas.resize((width, height), Image.LANCZOS)


def hero(width=800, height=300) -> Image.Image:
    """The banner behind the title: navy, warmed on the left, cooled on the right."""
    canvas = Image.new("RGBA", (width, height), NAVY + (255,))
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)
    for y in range(height):
        blend = y / height
        colour = tuple(
            int(NAVY[channel] + (NAVY_UP[channel] - NAVY[channel]) * blend) for channel in range(3)
        )
        draw.line([(0, y), (width, y)], fill=colour + (255,))
    canvas.alpha_composite(gradient)

    blooms = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bloom_draw = ImageDraw.Draw(blooms)
    for cx, cy, radius, colour, alpha in [
        (width * 0.14, height * 0.34, 165, ORANGE, 135),
        (width * 0.40, height * 0.10, 130, ORANGE_DEEP, 80),
        (width * 0.84, height * 0.26, 175, SKY_BRIGHT, 120),
        (width * 0.66, height * 0.90, 190, CYAN, 70),
        (width * 0.97, height * 0.80, 120, NEEKO_PINK, 45),
    ]:
        bloom_draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius], fill=colour + (alpha,)
        )
    canvas.alpha_composite(blooms.filter(ImageFilter.GaussianBlur(60)))

    petals = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    small = flower(120).resize((96, 96), Image.LANCZOS)
    faint = flower(120, petal=PEACH, centre=SKY).resize((64, 64), Image.LANCZOS)
    # Kept away from the top-right: the window buttons live over that corner.
    petals.alpha_composite(_fade(small, 70), (int(width * 0.58), int(height * 0.60)))
    petals.alpha_composite(_fade(faint, 55), (int(width * 0.05), int(height * 0.16)))
    petals.alpha_composite(_fade(faint, 40), (int(width * 0.30), int(height * 0.74)))
    canvas.alpha_composite(petals)
    return canvas


def _fade(image: Image.Image, alpha: int) -> Image.Image:
    faded = image.copy()
    faded.putalpha(image.getchannel("A").point(lambda value: value * alpha // 255))
    return faded


def icon() -> Image.Image:
    """App icon: the orange flower on a navy tile, readable down to 16px."""
    size = 1024
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=NAVY_UP + (255,))

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [size * 0.10, size * 0.10, size * 0.90, size * 0.90], fill=ORANGE_DEEP + (185,)
    )
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))

    petal = flower(int(size * 0.78))
    canvas.alpha_composite(petal, (int(size * 0.11), int(size * 0.11)))
    return canvas


def main() -> None:
    NEEKO.mkdir(parents=True, exist_ok=True)

    flower().save(NEEKO / "flower.png")
    flower(256, petal=PEACH, centre=SKY).save(NEEKO / "flower_soft.png")
    leaf().save(NEEKO / "leaf.png")
    hero().save(NEEKO / "hero_bg.png")

    art = icon()
    art.resize((256, 256), Image.LANCZOS).save(
        ASSETS / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    art.resize((256, 256), Image.LANCZOS).save(ASSETS / "icon.png")

    for name in ("flower.png", "flower_soft.png", "leaf.png", "hero_bg.png"):
        print(f"  {name:16} {(NEEKO / name).stat().st_size:>8,} bytes")
    print(f"  icon.ico         {(ASSETS / 'icon.ico').stat().st_size:>8,} bytes")


if __name__ == "__main__":
    main()
