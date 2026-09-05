"""Settings on disk.

Everything the user configures lives in one JSON file. Reading it is defensive
on purpose: a BOM left by a Windows editor, a truncated write, or a file full of
nonsense all end the same way -- the bad file is kept aside and a fresh default
config is written, rather than the app refusing to start.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_DIR_NAME = "NeekoDraftAssistant"

_APPDATA = Path(os.environ.get("APPDATA", Path.home()))
CONFIG_DIR = _APPDATA / APP_DIR_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"

# Where the queue-only version of this app kept its settings.
LEGACY_CONFIG_FILE = _APPDATA / "QueueAutoAccept" / "config.json"

MAX_DELAY = 10.0
MAX_MESSAGE = 200


@dataclass
class Settings:
    # queue
    auto_accept: bool = True
    accept_delay: float = 0.0
    sound: bool = True
    sound_file: str = ""      # empty means the built-in chime

    # champion select
    auto_declare: bool = True
    auto_pick: bool = False          # off by default: locking in is irreversible
    preferred_champion_id: int = 0
    preferred_champion_name: str = ""
    backup_champion_id: int = 0
    backup_champion_name: str = ""

    # chat
    chat_enabled: bool = False
    chat_message: str = "hello gl hf"

    # application
    auto_check_updates: bool = True
    minimize_to_tray: bool = True
    launch_minimized: bool = False
    animations: bool = True
    debug_logging: bool = False

    # counters
    accepted_total: int = 0
    picks_total: int = 0

    # -- loading ---------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None, legacy_path: Path | None = None) -> "Settings":
        config_file = path or CONFIG_FILE
        # The old queue-only config is only looked for at the real location,
        # unless a caller points somewhere else on purpose.
        legacy_file = legacy_path or (LEGACY_CONFIG_FILE if path is None else None)
        raw = _read_json(config_file)

        if raw is None and legacy_file is not None:
            legacy = _read_json(legacy_file)
            if isinstance(legacy, dict):
                settings = cls._from_dict(_migrate_legacy(legacy))
                settings.save(config_file)
                return settings

        if raw is None:
            settings = cls()
            settings.save(config_file)
            return settings

        if not isinstance(raw, dict):
            _quarantine(config_file)
            settings = cls()
            settings.save(config_file)
            return settings

        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, raw: dict) -> "Settings":
        known = {entry.name: entry for entry in fields(cls)}
        values = {}
        for key, value in raw.items():
            entry = known.get(key)
            if entry is None:
                continue  # a setting from a newer build; drop it quietly
            try:
                values[key] = _coerce(entry.type, value)
            except (TypeError, ValueError):
                continue  # keep the default for this one field
        settings = cls(**values)
        settings.normalise()
        return settings

    def normalise(self) -> None:
        self.accept_delay = min(max(float(self.accept_delay), 0.0), MAX_DELAY)
        self.preferred_champion_id = max(0, int(self.preferred_champion_id))
        self.backup_champion_id = max(0, int(self.backup_champion_id))
        self.chat_message = str(self.chat_message)[:MAX_MESSAGE]
        # A cue that has been deleted or unplugged is left in place rather
        # than quietly forgotten: the chime stands in until it is back.
        self.sound_file = str(self.sound_file)
        self.accepted_total = max(0, int(self.accepted_total))
        self.picks_total = max(0, int(self.picks_total))

    # -- saving ----------------------------------------------------------

    def save(self, path: Path | None = None) -> bool:
        config_file = path or CONFIG_FILE
        self.normalise()
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            # Write beside the real file and swap it in, so a crash mid-write
            # cannot leave a half-written config behind.
            temporary = config_file.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
            )
            os.replace(temporary, config_file)
            return True
        except OSError:
            return False  # a read-only profile is not worth crashing over


def _read_json(path: Path):
    """Parsed JSON, or None when the file is missing, unreadable or broken."""
    try:
        text = path.read_text(encoding="utf-8-sig")  # utf-8-sig also eats a BOM
    except OSError:
        return None
    try:
        return json.loads(text)
    except ValueError:
        _quarantine(path)
        return None


def _quarantine(path: Path) -> None:
    """Keep a broken config for inspection instead of silently deleting it."""
    try:
        path.replace(path.with_name(path.name + ".corrupt"))
    except OSError:
        pass


def _coerce(annotation, value):
    text = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")
    if "bool" in text:
        return bool(value)
    if "float" in text:
        return float(value)
    if "int" in text:
        return int(value)
    return str(value)


def _migrate_legacy(legacy: dict) -> dict:
    """Carry the queue-only settings over, counter included."""
    return {
        "auto_accept": legacy.get("enabled", True),
        "accept_delay": legacy.get("delay", 0.0),
        "sound": legacy.get("sound", True),
        "minimize_to_tray": legacy.get("minimize_to_tray", True),
        "accepted_total": legacy.get("accepted_total", 0),
    }
