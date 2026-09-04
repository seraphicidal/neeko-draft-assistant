"""The tray menu and the pause switch.

The menu is driven through its actions rather than by clicking, which is enough
to prove the wiring: toggles reach the settings, and Pause mutes the assistant
without editing anything the user configured.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.logbook import LogBook  # noqa: E402
from core.settings import Settings  # noqa: E402
from core.watcher import Watcher, _Paused  # noqa: E402
from league.champions import Catalog  # noqa: E402
from tests.mocks import FakeLcu  # noqa: E402

try:
    from PySide6.QtWidgets import QApplication

    from ui.tray import Tray

    QT_AVAILABLE = True
except Exception:  # pragma: no cover - only when PySide6 is missing
    QT_AVAILABLE = False


class PauseTest(unittest.TestCase):
    def test_pause_switches_every_automatic_action_off(self):
        settings = Settings(
            auto_accept=True, auto_declare=True, auto_pick=True, chat_enabled=True
        )

        paused = _Paused(settings)

        self.assertFalse(paused.auto_accept)
        self.assertFalse(paused.auto_declare)
        self.assertFalse(paused.auto_pick)
        self.assertFalse(paused.chat_enabled)

    def test_pause_leaves_the_real_settings_alone(self):
        settings = Settings(auto_accept=True, accept_delay=2.5, chat_message="gl hf")

        paused = _Paused(settings)

        self.assertEqual(paused.accept_delay, 2.5)      # non-automatic settings pass through
        self.assertEqual(paused.chat_message, "gl hf")
        self.assertTrue(settings.auto_accept)           # the original is untouched

    def test_the_watcher_hands_the_paused_view_to_the_machine(self):
        watcher = Watcher(Settings(), Catalog(), LogBook(), lambda *_: None, connect=FakeLcu)

        self.assertIs(watcher.active_settings, watcher.settings)

        watcher.paused = True
        self.assertIsInstance(watcher.active_settings, _Paused)
        self.assertFalse(watcher.active_settings.auto_accept)


@unittest.skipUnless(QT_AVAILABLE, "PySide6 is not installed")
class TrayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings = Settings()
        self.tray = Tray(self.settings)
        self.emitted: list[tuple[str, bool]] = []
        self.tray.setting_toggled.connect(lambda name, value: self.emitted.append((name, value)))

    def test_the_menu_offers_every_switch(self):
        labels = [action.text() for action in self.tray.contextMenu().actions()]

        for expected in ("Auto Accept", "Auto Declare", "Auto Pick", "Auto Chat",
                         "Open App", "Settings", "Pause", "Exit"):
            self.assertIn(expected, labels)

    def test_toggling_a_menu_entry_reports_the_change(self):
        self.tray.accept_action.setChecked(False)

        self.assertEqual(self.emitted, [("auto_accept", False)])

    def test_pause_emits_without_touching_settings(self):
        paused = []
        self.tray.pause_toggled.connect(paused.append)

        self.tray.pause_action.setChecked(True)

        self.assertEqual(paused, [True])
        self.assertTrue(self.settings.auto_accept)

    def test_sync_mirrors_settings_without_bouncing_signals(self):
        self.settings.auto_pick = True
        self.settings.chat_enabled = True

        self.tray.sync()

        self.assertTrue(self.tray.pick_action.isChecked())
        self.assertTrue(self.tray.chat_action.isChecked())
        self.assertEqual(self.emitted, [])  # sync must not look like a user click

    def test_status_line_shows_the_connection(self):
        self.tray.set_status(True, "Champion select")

        self.assertIn("Champion select", self.tray.status_action.text())
        self.assertTrue(self.tray.status_action.text().startswith("●"))

        self.tray.set_status(False, "Waiting for League Client...")
        self.assertTrue(self.tray.status_action.text().startswith("○"))


if __name__ == "__main__":
    unittest.main()
