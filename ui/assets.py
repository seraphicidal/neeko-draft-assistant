"""Where the pictures live.

Two kinds of art sit in ``assets/neeko``: the generated decorations that ship
with the app, and drop-in slots for your own Neeko pictures. Drop a file with
one of the slot names in and the UI picks it up on the next start; leave it out
and the app falls back to what it has.
"""

from __future__ import annotations

from pathlib import Path

from core.paths import assets_dir, program_dir

ASSETS = assets_dir()
NEEKO = ASSETS / "neeko"
# A packaged build also looks beside the executable, so drop-in art can be
# added without unpacking anything.
USER_NEEKO = program_dir() / "neeko"

ICON = ASSETS / "icon.ico"
ICON_PNG = ASSETS / "icon.png"

HERO_BG = NEEKO / "hero_bg.png"
FLOWER = NEEKO / "flower.png"
FLOWER_SOFT = NEEKO / "flower_soft.png"
LEAF = NEEKO / "leaf.png"

# Drop-in slots, in the order the avatar prefers them. Any image works; a GIF
# animates. `neeko_wink.gif` ships with the app.
AVATAR_SLOTS = (
    NEEKO / "avatar.gif",
    NEEKO / "avatar.png",
    NEEKO / "portrait.png",
    NEEKO / "neeko_wink.gif",
)

# Extra slots the settings screen tells you about, used as accents when present.
CHIBI_SLOTS = (NEEKO / "chibi.png", NEEKO / "chibi.gif")
STICKER_SLOTS = (NEEKO / "sticker.png", NEEKO / "sticker.gif")
FULL_SLOTS = (NEEKO / "full.png", NEEKO / "full.jpg")

SLOT_HELP = [
    (AVATAR_SLOTS, "avatar.gif / avatar.png", "round portrait at the top"),
    (CHIBI_SLOTS, "chibi.png", "accent art during champion select"),
    (STICKER_SLOTS, "sticker.png", "shown when a queue is accepted"),
    (FULL_SLOTS, "full.png", "art behind the header"),
]


def first_existing(candidates) -> Path | None:
    """Prefer the user's own drop-in folder, then what ships with the app."""
    for candidate in candidates:
        beside_exe = USER_NEEKO / candidate.name
        if beside_exe != candidate and beside_exe.exists():
            return beside_exe
        if candidate.exists():
            return candidate
    return None


def avatar() -> Path | None:
    return first_existing(AVATAR_SLOTS)


def chibi() -> Path | None:
    return first_existing(CHIBI_SLOTS)


def sticker() -> Path | None:
    return first_existing(STICKER_SLOTS)


def full_art() -> Path | None:
    return first_existing(FULL_SLOTS)


def is_animated(path: Path | None) -> bool:
    return bool(path and path.suffix.lower() == ".gif")
