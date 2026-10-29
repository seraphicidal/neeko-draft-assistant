
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

OK = "ok"
INFO = "info"
WARN = "warn"
ERROR = "error"
DEBUG = "debug"


@dataclass(frozen=True)
class Entry:
    at: datetime
    level: str
    text: str

    def __str__(self) -> str:
        return f"[{self.at:%H:%M:%S}] {self.text}"


class LogBook:

    def __init__(self, capacity: int = 500, file_path: Path | None = None) -> None:
        self._entries: deque[Entry] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self.debug_enabled = False
        self.file_path = Path(file_path) if file_path else None

    def add(self, level: str, text: str) -> Entry | None:
        if level == DEBUG and not self.debug_enabled:
            return None
        entry = Entry(datetime.now(), level, text)
        with self._lock:
            self._entries.append(entry)
            self._write_file(entry)
        return entry

    def _write_file(self, entry: Entry) -> None:
        if not self.file_path:
            return
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            if self.file_path.exists() and self.file_path.stat().st_size > 2 * 1024 * 1024:
                backup = self.file_path.with_suffix(".log.1")
                backup.unlink(missing_ok=True)
                self.file_path.replace(backup)
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(f"[{entry.at:%Y-%m-%d %H:%M:%S}] [{entry.level.upper()}] {entry.text}\n")
        except OSError:
            pass

    def entries(self) -> list[Entry]:
        with self._lock:
            return list(self._entries)

    def as_text(self) -> str:
        return "\n".join(str(entry) for entry in self.entries())

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
