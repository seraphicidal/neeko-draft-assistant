"""Where the pictures live.

Two kinds of art sit in `assets/neeko`: what ships with the app, and drop-in
files you can add yourself. A packaged build also looks in a `neeko` folder
beside the executable, so nothing has to be unpacked to swap an illustration.
"""

from __future__ import annotations

from pathlib import Path

from core.paths import assets_dir, program_dir

ASSETS = assets_dir()
NEEKO = ASSETS / "neeko"
USER_NEEKO = program_dir() / "neeko"

ICON = ASSETS / "icon.ico"
ICON_PNG = ASSETS / "icon.png"

FLOWER = NEEKO / "flower.png"
HERO_BG = NEEKO / "hero_bg.png"

# The header portrait, in order of preference. A GIF animates.
AVATAR_SLOTS = (
    NEEKO / "avatar.gif",
    NEEKO / "avatar.png",
    NEEKO / "neeko_wink.gif",
    NEEKO / "portrait.png",
)

# One illustration per situation, keyed by the roles in ui/status.py.
ART_SLOTS = {
    "mood_idle": ("mood_idle.png", "waiting for the League client"),
    "mood_happy": ("mood_happy.png", "connected, lobby and post-game"),
    "mood_alert": ("mood_alert.png", "match found and your turn to pick"),
    "mood_calm": ("mood_calm.png", "locked in and in game"),
    "portrait": ("portrait.png", "champion select"),
}


def _resolve(name: str) -> Path | None:
    """Your own copy first, then the one that ships with the app."""
    beside_executable = USER_NEEKO / name
    if beside_executable.exists():
        return beside_executable
    bundled = NEEKO / name
    return bundled if bundled.exists() else None


def first_existing(candidates) -> Path | None:
    for candidate in candidates:
        found = _resolve(Path(candidate).name)
        if found is not None:
            return found
    return None


def avatar() -> Path | None:
    return first_existing(AVATAR_SLOTS)


def art(role: str) -> Path | None:
    """The illustration for a status role, or None if it is not installed."""
    entry = ART_SLOTS.get(role)
    return _resolve(entry[0]) if entry else None


def missing_art() -> list[str]:
    """Roles with no illustration, so the About page can be honest about it."""
    return [role for role in ART_SLOTS if art(role) is None]


def slot_help() -> list[tuple[str, str, bool]]:
    """`(filename, what it is for, present)` for every drop-in slot."""
    entries = [("avatar.gif / avatar.png", "the portrait in the header", avatar() is not None)]
    entries += [
        (filename, purpose, art(role) is not None)
        for role, (filename, purpose) in ART_SLOTS.items()
    ]
    return entries
