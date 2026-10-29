
from __future__ import annotations

from pathlib import Path

from core.paths import assets_dir, program_dir

ASSETS = assets_dir()
NEEKO = ASSETS / "neeko"
USER_NEEKO = program_dir() / "neeko"

ICON = ASSETS / "icon.ico"
ICON_PNG = ASSETS / "icon.png"


def app_icon():
    from PySide6.QtGui import QIcon

    icon = QIcon(str(ICON))
    if ICON_PNG.exists():
        icon.addFile(str(ICON_PNG))
    return icon

FLOWER = NEEKO / "flower.png"
HERO_BG = NEEKO / "hero_bg.png"

AVATAR_SLOTS = (
    NEEKO / "avatar.gif",
    NEEKO / "avatar.png",
    NEEKO / "neeko_wink.gif",
    NEEKO / "portrait.png",
)

ART_SLOTS = {
    "mood_idle": ("mood_idle.png", "waiting for the League client"),
    "mood_happy": ("mood_happy.png", "connected, lobby and post-game"),
    "mood_alert": ("mood_alert.png", "match found and your turn to pick"),
    "mood_calm": ("mood_calm.png", "locked in and in game"),
    "portrait": ("portrait.png", "champion select"),
}


def _resolve(name: str) -> Path | None:
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
    entry = ART_SLOTS.get(role)
    return _resolve(entry[0]) if entry else None


def missing_art() -> list[str]:
    return [role for role in ART_SLOTS if art(role) is None]


def slot_help() -> list[tuple[str, str, bool]]:
    entries = [("avatar.gif / avatar.png", "the portrait in the header", avatar() is not None)]
    entries += [
        (filename, purpose, art(role) is not None)
        for role, (filename, purpose) in ART_SLOTS.items()
    ]
    return entries
