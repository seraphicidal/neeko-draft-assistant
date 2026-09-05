"""Run the real UI against a scripted stand-in client. Development only.

Champion select cannot be summoned on demand, so this drives the actual window,
watcher and state machine with the fake client from the test suite. Nothing here
ships in the app, and it never touches your real settings.

    python tools/preview.py [scenario]

    offline    League is not running          draft     champion select
    connected  client open, nothing happening myturn    your pick is live
    queue      searching for a match          game      in game
    ready      the queue pop                  settings  the settings window
    pick       the champion search overlay    about     the About page
    sound      the sound cue settings
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from league import champion_select as cs, chat, gameflow, matchmaking as mm  # noqa: E402
from league.lcu_client import ClientUnavailable  # noqa: E402
from ui.settings_window import SECTIONS as SETTINGS_SECTIONS  # noqa: E402
from tests.mocks import (  # noqa: E402
    FakeLcu,
    action,
    conversations_payload,
    ready_check_payload,
    session_payload,
)

NEEKO, AHRI = 518, 103
SUMMONER = "/lol-summoner/v1/current-summoner"


def base(phase: str, routes: dict | None = None) -> FakeLcu:
    return FakeLcu(
        {
            gameflow.ENDPOINT: (200, phase),
            SUMMONER: (200, {"gameName": "Miska"}),
            **(routes or {}),
        }
    )


def draft(my_turn: bool) -> FakeLcu:
    actions = [
        [
            action(3, cell=7, kind="ban", champion=AHRI, completed=True),
            action(5, cell=2, in_progress=my_turn),
        ]
    ]
    return base(
        "ChampSelect",
        {
            cs.SESSION: (
                200,
                session_payload(local_cell=2, actions=actions, time_left_ms=18000),
            ),
            cs.PICKABLE: (200, [NEEKO, AHRI]),
            ("PATCH", cs.ACTION.format(action_id=5)): (204, None),
            chat.CONVERSATIONS: (200, conversations_payload("draft@sec")),
            ("POST", chat.MESSAGES.format(conversation_id="draft@sec")): (200, {"id": "1"}),
        },
    )


SCENARIOS = {
    "connected": lambda: base("None"),
    "queue": lambda: base("Matchmaking"),
    "ready": lambda: base(
        "ReadyCheck",
        {mm.READY_CHECK: (200, ready_check_payload()), ("POST", mm.ACCEPT): (204, None)},
    ),
    "draft": lambda: draft(my_turn=False),
    "myturn": lambda: draft(my_turn=True),
    "game": lambda: base("InProgress"),
    "settings": lambda: draft(my_turn=False),
    "about": lambda: base("None"),
    "pick": lambda: base("None"),
    "sound": lambda: base("None"),
}

# Which settings page each settings scenario opens on.
SETTINGS_PAGE = {"about": "About", "sound": "Queue"}


def _a_sound_file(folder: Path) -> Path:
    """Half a second of a sine wave, so the cue settings have something to show."""
    import math
    import struct
    import wave

    path = folder / "my cue.wav"
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(22050)
        handle.writeframes(
            b"".join(
                struct.pack("<h", int(6000 * math.sin(2 * math.pi * 660 * frame / 22050)))
                for frame in range(11025)
            )
        )
    return path


def main() -> int:
    scenario = sys.argv[1] if len(sys.argv) > 1 else "draft"

    from core import settings as settings_module

    temporary = Path(tempfile.mkdtemp(prefix="neeko-preview-")) / "config.json"
    settings_module.CONFIG_FILE = temporary
    settings_module.LEGACY_CONFIG_FILE = temporary.with_name("nothing.json")

    from ui.app import Application

    app = Application([])
    app.settings.preferred_champion_id = NEEKO
    app.settings.preferred_champion_name = "Neeko"
    app.settings.backup_champion_id = AHRI
    app.settings.backup_champion_name = "Ahri"
    app.settings.chat_enabled = True
    app.settings.chat_message = "hello gl hf"
    app.settings.accepted_total = 37
    app.settings.picks_total = 12
    # A long delay keeps the ready-check countdown on screen to be looked at.
    app.settings.accept_delay = 8.0 if scenario == "ready" else 2.5
    if scenario == "sound":
        app.settings.sound_file = str(_a_sound_file(temporary.parent))
    app.window._load_from_settings()

    if scenario == "offline":
        def refuse():
            raise ClientUnavailable("preview: no client")

        app.watcher._connect_client = refuse
    else:
        client = SCENARIOS.get(scenario, SCENARIOS["draft"])()
        app.watcher._connect_client = lambda: client

    if scenario in ("settings", "about", "sound"):
        from PySide6.QtCore import QTimer

        def open_settings() -> None:
            app.open_settings()
            page = SETTINGS_PAGE.get(scenario)
            if page:
                app.settings_window.nav.setCurrentRow(SETTINGS_SECTIONS.index(page))

        QTimer.singleShot(700, open_settings)
    elif scenario == "pick":
        from PySide6.QtCore import QTimer

        QTimer.singleShot(700, lambda: app.window._open_overlay("primary"))
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
