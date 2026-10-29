
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

EXTENSIONS = (".mp3", ".wav", ".m4a", ".wma", ".aac", ".ogg", ".flac")
FILE_FILTER = "Audio (*.mp3 *.wav *.m4a *.wma *.aac *.ogg *.flac)"

MAX_BYTES = 20 * 1024 * 1024

TONES = ((988, 90), (1319, 130))


class SoundError(Exception):
    pass


def _mci(command: str) -> bool:
    if sys.platform != "win32":
        return False
    try:
        buffer = ctypes.create_unicode_buffer(255)
        return ctypes.windll.winmm.mciSendStringW(command, buffer, 254, None) == 0
    except Exception:
        return False


def _tones() -> None:
    if sys.platform != "win32":
        return
    try:
        import winsound

        for hertz, milliseconds in TONES:
            winsound.Beep(hertz, milliseconds)
    except Exception:
        pass


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(name).name).strip(". ")
    return cleaned or "cue.mp3"


def install(source: str | Path) -> Path:
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


class Cue:

    def __init__(self, send=_mci, beep=_tones) -> None:
        self._send = send
        self._beep = beep
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._alias = "neekocue"
        self._holding = False

    def play(self, path: str | Path = "") -> None:
        self._start()
        self._queue.put(str(path or ""))

    def stop(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self._queue.put(None)
            self._thread.join(timeout=1.0)
        self._thread = None

    def playable(self, path: str | Path) -> bool:
        path = Path(path)
        if not path.is_file():
            return False
        opened = self._send(f'open "{path}" alias {self._alias}check')
        if opened:
            self._send(f"close {self._alias}check")
        return opened

    def _start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
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
            except Exception:
                pass

    def play_once(self, path: str) -> bool:
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
        if self._holding:
            self._send(f"close {self._alias}")
            self._holding = False
