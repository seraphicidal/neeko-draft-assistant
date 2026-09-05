"""The little noise the app makes when it answers a queue.

Two tones out of the PC speaker by default, or a sound file of the user's own.
Playback goes through MCI -- the sound interface that has been part of Windows
since forever -- because it plays MP3 with nothing installed and nothing
bundled: the alternative, Qt's multimedia stack, would have added tens of
megabytes to the installer for one chime.

Every MCI call is made on one long-lived thread. That is not tidiness: MCI
closes whatever a thread opened when that thread ends, so a cue played from a
short-lived worker would be cut off mid-note.
"""

from __future__ import annotations

import ctypes
import queue
import re
import shutil
import sys
import threading
from pathlib import Path

from core.settings import CONFIG_DIR

SOUNDS_DIR = CONFIG_DIR / "sounds"

# What the file dialog offers. MP3 and WAV always work; the rest depend on the
# codecs Windows has, and fall back to the built-in tones if one is missing.
EXTENSIONS = (".mp3", ".wav", ".m4a", ".wma", ".aac", ".ogg", ".flac")
FILE_FILTER = "Audio (*.mp3 *.wav *.m4a *.wma *.aac *.ogg *.flac)"

# Big enough for any cue, small enough that a copy into the settings folder is
# instant and a mis-picked video file is refused.
MAX_BYTES = 20 * 1024 * 1024

TONES = ((988, 90), (1319, 130))   # the default chime, in (hertz, milliseconds)


class SoundError(Exception):
    """The file cannot be used as a cue, with a sentence saying why."""


# -- the Windows side ------------------------------------------------------


def _mci(command: str) -> bool:
    """One MCI command. True when Windows accepted it."""
    if sys.platform != "win32":
        return False
    try:
        buffer = ctypes.create_unicode_buffer(255)
        return ctypes.windll.winmm.mciSendStringW(command, buffer, 254, None) == 0
    except Exception:  # a machine without winmm is a machine without a cue
        return False


def _tones() -> None:
    """The default two-note chime."""
    if sys.platform != "win32":
        return
    try:
        import winsound

        for hertz, milliseconds in TONES:
            winsound.Beep(hertz, milliseconds)
    except Exception:  # a missing beep is not worth an error
        pass


# -- choosing a file -------------------------------------------------------


def _safe_name(name: str) -> str:
    """A file name Windows will take, whatever the original was called."""
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(name).name).strip(". ")
    return cleaned or "cue.mp3"


def install(source: str | Path) -> Path:
    """Copy a chosen sound in beside the settings.

    Kept as our own copy on purpose: a cue that lived on the desktop would go
    silent the day the file was moved, and the reason would not be obvious.
    """
    source = Path(source)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise SoundError("That file could not be read.") from exc
    if size > MAX_BYTES:
        raise SoundError(f"That file is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    if source.suffix.lower() not in EXTENSIONS:
        raise SoundError("That is not a sound file Neeko can play.")

    target = SOUNDS_DIR / _safe_name(source.name)
    try:
        SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
        if not (target.exists() and source.resolve() == target.resolve()):
            shutil.copyfile(source, target)
    except OSError as exc:
        raise SoundError("The sound could not be copied into the settings folder.") from exc
    return target


# -- playing it ------------------------------------------------------------


class Cue:
    """Plays the accept cue. One instance, one thread, one sound at a time."""

    def __init__(self, send=_mci, beep=_tones) -> None:
        self._send = send
        self._beep = beep
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._alias = "neekocue"
        self._holding = False

    # -- what the app calls ------------------------------------------------

    def play(self, path: str | Path = "") -> None:
        """Play `path`, or the built-in chime when it is empty or unplayable."""
        self._start()
        self._queue.put(str(path or ""))

    def stop(self) -> None:
        if self._thread is not None:
            self._queue.put(None)

    def playable(self, path: str | Path) -> bool:
        """Can Windows open this file? Answered without making a sound."""
        path = Path(path)
        if not path.is_file():
            return False
        opened = self._send(f'open "{path}" alias {self._alias}check')
        if opened:
            self._send(f"close {self._alias}check")
        return opened

    # -- the thread --------------------------------------------------------

    def _start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="neeko-sound", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._release()
                return
            try:
                self.play_once(item)
            except Exception:  # a cue is never worth taking the app down for
                pass

    # -- one cue -----------------------------------------------------------

    def play_once(self, path: str) -> bool:
        """True when the file played, False when the chime stood in for it.

        Public so the behaviour can be tested without a sound card.
        """
        self._release()
        if path and Path(path).is_file():
            if self._send(f'open "{path}" alias {self._alias}'):
                self._holding = True
                if self._send(f"play {self._alias} from 0"):
                    return True
                self._release()
        self._beep()
        return False

    def _release(self) -> None:
        """Let go of the previous sound, so a new cue replaces it."""
        if self._holding:
            self._send(f"close {self._alias}")
            self._holding = False
