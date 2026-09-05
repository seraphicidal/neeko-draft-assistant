"""Settings survive restarts, bad editors and broken files."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.settings import MAX_DELAY, Settings


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self._temp = TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.path = Path(self._temp.name) / "config.json"

    def test_missing_file_writes_defaults(self):
        settings = Settings.load(self.path)

        self.assertTrue(self.path.exists())
        self.assertTrue(settings.auto_accept)
        self.assertFalse(settings.auto_pick)  # locking in is opt-in

    def test_everything_survives_a_round_trip(self):
        settings = Settings.load(self.path)
        settings.preferred_champion_id = 518
        settings.preferred_champion_name = "Neeko"
        settings.backup_champion_id = 103
        settings.auto_pick = True
        settings.chat_enabled = True
        settings.chat_message = "hello gl hf"
        settings.accept_delay = 2.5
        settings.sound_file = r"C:\Users\miska\cue.mp3"
        settings.launch_minimized = True
        settings.accepted_total = 12
        settings.save(self.path)

        reloaded = Settings.load(self.path)

        self.assertEqual(reloaded.preferred_champion_id, 518)
        self.assertEqual(reloaded.preferred_champion_name, "Neeko")
        self.assertEqual(reloaded.backup_champion_id, 103)
        self.assertTrue(reloaded.auto_pick)
        self.assertTrue(reloaded.chat_enabled)
        self.assertEqual(reloaded.chat_message, "hello gl hf")
        self.assertEqual(reloaded.accept_delay, 2.5)
        self.assertEqual(reloaded.sound_file, r"C:\Users\miska\cue.mp3")
        self.assertTrue(reloaded.launch_minimized)
        self.assertEqual(reloaded.accepted_total, 12)

    def test_a_byte_order_mark_is_tolerated(self):
        # Notepad and PowerShell both leave one behind.
        payload = json.dumps({"accept_delay": 4.0, "chat_message": "gl"})
        self.path.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))

        settings = Settings.load(self.path)

        self.assertEqual(settings.accept_delay, 4.0)
        self.assertEqual(settings.chat_message, "gl")

    def test_a_broken_file_is_kept_aside_and_replaced(self):
        self.path.write_text("{ this is not json", encoding="utf-8")

        settings = Settings.load(self.path)

        self.assertTrue(settings.auto_accept)  # fresh defaults, no crash
        self.assertTrue(self.path.with_name(self.path.name + ".corrupt").exists())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["auto_accept"], True)

    def test_a_json_file_that_is_not_an_object_is_replaced(self):
        self.path.write_text("[1, 2, 3]", encoding="utf-8")

        self.assertTrue(Settings.load(self.path).auto_accept)

    def test_unknown_and_mistyped_fields_do_not_break_the_load(self):
        self.path.write_text(
            json.dumps(
                {"auto_accept": False, "accept_delay": "not a number", "from_the_future": 1}
            ),
            encoding="utf-8",
        )

        settings = Settings.load(self.path)

        self.assertFalse(settings.auto_accept)     # the good field is kept
        self.assertEqual(settings.accept_delay, 0.0)  # the bad one falls back
        self.assertFalse(hasattr(settings, "from_the_future"))

    def test_values_are_clamped(self):
        settings = Settings.load(self.path)
        settings.accept_delay = 999.0
        settings.preferred_champion_id = -5
        settings.chat_message = "x" * 500
        settings.save(self.path)

        reloaded = Settings.load(self.path)

        self.assertEqual(reloaded.accept_delay, MAX_DELAY)
        self.assertEqual(reloaded.preferred_champion_id, 0)
        self.assertEqual(len(reloaded.chat_message), 200)

    def test_the_queue_only_config_is_migrated(self):
        legacy = Path(self._temp.name) / "legacy.json"
        legacy.write_text(
            json.dumps(
                {"enabled": False, "delay": 3.0, "sound": False,
                 "minimize_to_tray": False, "accepted_total": 42}
            ),
            encoding="utf-8",
        )

        migrated = Settings.load(self.path, legacy_path=legacy)

        self.assertFalse(migrated.auto_accept)     # old "enabled"
        self.assertEqual(migrated.accept_delay, 3.0)
        self.assertFalse(migrated.sound)
        self.assertFalse(migrated.minimize_to_tray)
        self.assertEqual(migrated.accepted_total, 42)


if __name__ == "__main__":
    unittest.main()
