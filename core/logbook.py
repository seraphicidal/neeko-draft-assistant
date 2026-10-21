
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime

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

    def __init__(self, capacity: int = 500) -> None:
        self._entries: deque[Entry] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self.debug_enabled = False

    def add(self, level: str, text: str) -> Entry | None:
        if level == DEBUG and not self.debug_enabled:
            return None
        entry = Entry(datetime.now(), level, text)
        with self._lock:
            self._entries.append(entry)
        return entry

    def entries(self) -> list[Entry]:
        with self._lock:
            return list(self._entries)

    def as_text(self) -> str:
        return "\n".join(str(entry) for entry in self.entries())

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
