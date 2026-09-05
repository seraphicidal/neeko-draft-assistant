"""Fetches champion icons and splash art off the GUI thread.

Requests are deduplicated and answered from the on-disk cache when possible, so
a champion is only ever downloaded once per machine.
"""

from __future__ import annotations

import queue
import threading
import time

from PySide6.QtCore import QObject, Signal

from league import champion_art
from league.lcu_client import ClientUnavailable, LcuClient, discover

# How long to leave a missing League client alone before looking again.
CLIENT_RETRY_SECONDS = 5.0


class ArtLoader(QObject):
    """Emits `loaded(kind, champion_id, data)` once the bytes are in hand."""

    loaded = Signal(str, int, bytes)

    def __init__(self, catalog, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self._queue: queue.Queue = queue.Queue()
        self._seen: set[tuple[str, int]] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._client: LcuClient | None = None
        self._client_retry_at = 0.0
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="neeko-art", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(None)

    def request(self, kind: str, champion_id: int) -> None:
        champion_id = int(champion_id or 0)
        if champion_id <= 0:
            return
        key = (kind, champion_id)
        with self._lock:
            if key in self._seen:
                return
            self._seen.add(key)
        self._queue.put(key)

    def forget(self, champion_id: int) -> None:
        """Allow a re-request, e.g. after the client came up and can serve art."""
        with self._lock:
            self._seen = {key for key in self._seen if key[1] != champion_id}

    # -- worker ----------------------------------------------------------

    def _lcu(self) -> LcuClient | None:
        """Its own client, so nothing is shared with the watcher thread.

        Looked for again every few seconds rather than once: the app is
        normally started before League is, and the client serves champion art
        without touching the internet, so it is worth waiting for.
        """
        if self._client is not None:
            return self._client
        now = time.monotonic()
        if now < self._client_retry_at:
            return None
        self._client_retry_at = now + CLIENT_RETRY_SECONDS
        try:
            self._client = LcuClient(discover())
        except ClientUnavailable:
            self._client = None
        return self._client

    def _run(self) -> None:
        while not self._stop.is_set():
            item = self._queue.get()
            if item is None:
                return
            kind, champion_id = item
            try:
                data = champion_art.load(
                    kind,
                    champion_id,
                    alias=self.catalog.alias_of(champion_id),
                    version=self.catalog.version,
                    client=self._lcu(),
                )
            except Exception:  # art is decoration; never take the app down for it
                data = None
            if data:
                self.loaded.emit(kind, champion_id, data)
            else:
                # Forgotten rather than remembered as failed: the next time
                # this champion is shown it gets another go, by which point
                # the client may well be up.
                with self._lock:
                    self._seen.discard((kind, champion_id))
