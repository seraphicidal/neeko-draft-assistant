"""The accept cue: the user's own sound, or the two tones that ship with it.

No sound is actually made here. The Windows side is one function taking one
command string, so the tests hand the player a fake one and read what it was
asked to do.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core import sound


class TempFolderMixin:
    def a_folder(self) -> Path:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)


class FakeWindows:
    """Stands in for MCI. Records commands, and can be told to refuse."""

    def __init__(self, accepts: bool = True) -> None:
        self.commands: list[str] = []
        self.accepts = accepts

    def __call__(self, command: str) -> bool:
        self.commands.append(command)
        return self.accepts

    def verbs(self) -> list[str]:
        return [command.split()[0] for command in self.commands]


class CueTest(TempFolderMixin, unittest.TestCase):
    def setUp(self):
        self.windows = FakeWindows()
        self.beeps = 0
        self.cue = sound.Cue(send=self.windows, beep=self._beep)
        self.folder = self.a_folder()
        self.file = self.folder / "victory.mp3"
        self.file.write_bytes(b"pretend this is an mp3")

    def _beep(self) -> None:
        self.beeps += 1

    def test_no_file_means_the_built_in_chime(self):
        self.assertFalse(self.cue.play_once(""))

        self.assertEqual(self.beeps, 1)
        self.assertEqual(self.windows.commands, [])

    def test_a_chosen_file_is_opened_and_played(self):
        self.assertTrue(self.cue.play_once(str(self.file)))

        self.assertEqual(self.windows.verbs(), ["open", "play"])
        self.assertIn(str(self.file), self.windows.commands[0])
        self.assertEqual(self.beeps, 0)

    def test_a_file_that_has_been_deleted_falls_back_to_the_chime(self):
        self.file.unlink()

        self.assertFalse(self.cue.play_once(str(self.file)))

        self.assertEqual(self.beeps, 1)
        self.assertEqual(self.windows.commands, [])

    def test_a_file_windows_will_not_open_falls_back_to_the_chime(self):
        self.cue = sound.Cue(send=FakeWindows(accepts=False), beep=self._beep)

        self.assertFalse(self.cue.play_once(str(self.file)))

        self.assertEqual(self.beeps, 1)

    def test_the_previous_sound_is_let_go_before_the_next_one(self):
        self.cue.play_once(str(self.file))
        self.cue.play_once(str(self.file))

        self.assertEqual(self.windows.verbs(), ["open", "play", "close", "open", "play"])

    def test_nothing_is_closed_that_was_never_opened(self):
        self.cue.play_once("")
        self.cue.play_once("")

        self.assertNotIn("close", self.windows.verbs())

    def test_playable_asks_without_making_a_sound(self):
        self.assertTrue(self.cue.playable(self.file))

        self.assertEqual(self.windows.verbs(), ["open", "close"])
        self.assertEqual(self.beeps, 0)

    def test_a_missing_file_is_not_playable(self):
        self.assertFalse(self.cue.playable(self.folder / "nothing.mp3"))
        self.assertEqual(self.windows.commands, [])


class InstallTest(TempFolderMixin, unittest.TestCase):
    def setUp(self):
        self.folder = self.a_folder()
        self.original = sound.SOUNDS_DIR
        sound.SOUNDS_DIR = self.folder / "sounds"

    def tearDown(self):
        sound.SOUNDS_DIR = self.original

    def source(self, name: str, size: int = 32) -> Path:
        path = self.folder / name
        path.write_bytes(b"x" * size)
        return path

    def test_the_file_is_copied_in_beside_the_settings(self):
        installed = sound.install(self.source("cue.mp3"))

        self.assertEqual(installed.parent, sound.SOUNDS_DIR)
        self.assertTrue(installed.is_file())

    def test_installing_the_same_file_twice_is_harmless(self):
        first = sound.install(self.source("cue.mp3"))
        second = sound.install(first)

        self.assertEqual(first, second)
        self.assertTrue(second.is_file())

    def test_an_awkward_name_is_made_safe(self):
        installed = sound.install(self.source("mišk@ ~ cue!.mp3"))

        self.assertTrue(installed.name.endswith(".mp3"))
        self.assertNotIn("@", installed.name)

    def test_something_that_is_not_a_sound_is_refused(self):
        with self.assertRaises(sound.SoundError):
            sound.install(self.source("notes.txt"))

    def test_an_enormous_file_is_refused(self):
        with self.assertRaises(sound.SoundError):
            sound.install(self.source("epic.wav", size=sound.MAX_BYTES + 1))

    def test_a_file_that_is_not_there_is_refused(self):
        with self.assertRaises(sound.SoundError):
            sound.install(self.folder / "ghost.mp3")


if __name__ == "__main__":
    unittest.main()
