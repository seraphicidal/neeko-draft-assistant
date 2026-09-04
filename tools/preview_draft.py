"""Run the real UI against a scripted stand-in client. Development only.

Champion select cannot be summoned on demand, so this drives the actual window,
watcher and state machine with the fake client from the test suite. Nothing here
ships in the app, and it never touches your real settings.

    python tools/preview_draft.py            my pick turn
    python tools/preview_draft.py queue      a queue pop
    python tools/preview_draft.py settings   the settings window
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import settings as settings_module  # noqa: E402
from league import champion_select as cs, chat, gameflow, matchmaking as mm  # noqa: E402
from tests.mocks import (  # noqa: E402
    FakeLcu,
    action,
    conversations_payload,
    ready_check_payload,
    session_payload,
)

NEEKO, AHRI = 518, 103
SUMMONER = "/lol-summoner/v1/current-summoner"


def draft_client() -> FakeLcu:
    return FakeLcu(
        {
            gameflow.ENDPOINT: (200, "ChampSelect"),
            SUMMONER: (200, {"gameName": "Chobot"}),
            cs.SESSION: (
                200,
                session_payload(
                    local_cell=2,
                    actions=[[action(3, cell=7, kind="ban", champion=AHRI, completed=True),
                              action(5, cell=2, in_progress=True)]],
                    time_left_ms=18000,
                ),
            ),
            cs.PICKABLE: (200, [NEEKO, AHRI]),
            ("PATCH", cs.ACTION.format(action_id=5)): (204, None),
            chat.CONVERSATIONS: (200, conversations_payload("draft@sec")),
            ("POST", chat.MESSAGES.format(conversation_id="draft@sec")): (200, {"id": "1"}),
        }
    )


def queue_client() -> FakeLcu:
    return FakeLcu(
        {
            gameflow.ENDPOINT: (200, "ReadyCheck"),
            SUMMONER: (200, {"gameName": "Chobot"}),
            mm.READY_CHECK: (200, ready_check_payload()),
            ("POST", mm.ACCEPT): (204, None),
        }
    )


def main() -> int:
    scenario = sys.argv[1] if len(sys.argv) > 1 else "draft"

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
    app.settings.accept_delay = 2.5
    app.settings.accepted_total = 37
    app.settings.picks_total = 12
    app.window._load_from_settings()

    client = queue_client() if scenario == "queue" else draft_client()
    app.watcher._connect_client = lambda: client

    if scenario == "settings":
        from PySide6.QtCore import QTimer

        QTimer.singleShot(600, app.open_settings)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
