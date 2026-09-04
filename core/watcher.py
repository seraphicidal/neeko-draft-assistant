"""The background loop: poll the client, ask the machine, carry out the answer.

The watcher owns all the I/O and none of the judgement. It builds a snapshot,
hands it to the state machine, and performs whatever intents come back --
reporting the result of each one so the machine can back off or stop trying.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Callable

from league import champion_select as cs
from league import chat, champions, gameflow, matchmaking
from league.lcu_client import ClientUnavailable, LcuClient, discover
from core import logbook
from core.state_machine import AppState, Intent, IntentKind, Snapshot, StateMachine

INTERVAL_DISCONNECTED = 2.0
INTERVAL_IDLE = 1.0
INTERVAL_QUEUE = 0.25
INTERVAL_DRAFT = 0.4

PICKABLE_REFRESH = 1.0
CHAT_LOOKUP_INTERVAL = 1.0


class _Paused:
    """A settings view with every automatic action switched off.

    Pausing from the tray must not overwrite what the user configured, so the
    real settings object is left alone and this stands in front of it.
    """

    AUTOMATIC = ("auto_accept", "auto_declare", "auto_pick", "chat_enabled")

    def __init__(self, settings) -> None:
        self._settings = settings

    def __getattr__(self, name):
        if name in self.AUTOMATIC:
            return False
        return getattr(self._settings, name)


@dataclass(frozen=True)
class StatusView:
    """Everything the main window shows, in one immutable lump."""

    connected: bool = False
    state: str = AppState.DISCONNECTED.value
    phase: str = "Unknown"
    phase_label: str = "Waiting for League Client..."
    detail: str = "Waiting for League Client..."
    problem: str = ""
    turn: str = ""
    time_left: float = 0.0
    accept_in: float = 0.0
    in_draft: bool = False
    chat_sent: bool = False
    chat_failed: bool = False
    declared_champion: int = 0
    summoner: str = ""


class Watcher(threading.Thread):
    def __init__(
        self,
        settings,
        catalog: champions.Catalog,
        log: logbook.LogBook,
        emit: Callable[[str, dict], None],
        connect: Callable[[], LcuClient] | None = None,
    ) -> None:
        super().__init__(name="neeko-watcher", daemon=True)
        self.settings = settings
        self.catalog = catalog
        self.log = log
        self.machine = StateMachine()
        self._emit = emit
        self._connect_client = connect or self._discover
        self._stop = threading.Event()

        self._client: LcuClient | None = None
        self._install_dir: str | None = None
        self._summoner = ""
        self._status = StatusView()

        self.paused = False
        self._portrait_lock = threading.Lock()
        self._portrait_wanted: list[int] = []
        self._portraits_done: set[int] = set()

        self._pickable: frozenset[int] | None = None
        self._pickable_at = 0.0
        self._chat_conversation: str | None = None
        self._chat_lookup_at = 0.0
        self._draft_identity = ""

    # -- lifecycle -------------------------------------------------------

    def stop(self) -> None:
        self._stop.set()

    @property
    def active_settings(self):
        """What the machine gets to see -- muted while paused."""
        return _Paused(self.settings) if self.paused else self.settings

    def request_portrait(self, champion_id: int) -> None:
        """Ask for a champion icon; it arrives later as a `portrait` event."""
        champion_id = int(champion_id)
        if champion_id <= 0:
            return
        with self._portrait_lock:
            if champion_id in self._portraits_done or champion_id in self._portrait_wanted:
                return
            self._portrait_wanted.append(champion_id)

    def _serve_one_portrait(self) -> None:
        """One icon per tick, so a burst of requests cannot stall the loop."""
        if self._client is None:
            return
        with self._portrait_lock:
            if not self._portrait_wanted:
                return
            champion_id = self._portrait_wanted.pop(0)
        try:
            data = self._client.get_bytes(champions.portrait_path(champion_id))
        except ClientUnavailable:
            with self._portrait_lock:
                self._portrait_wanted.append(champion_id)
            raise
        if data:
            with self._portrait_lock:
                self._portraits_done.add(champion_id)
            self._emit("portrait", {"champion_id": champion_id, "data": data})

    def run(self) -> None:
        self._publish(self._status)
        while not self._stop.is_set():
            try:
                interval = self._tick()
            except ClientUnavailable:
                interval = self._drop_client()
            except Exception as exc:  # a dead watcher thread would fail silently
                self._say(logbook.ERROR, f"Unexpected error: {exc}")
                interval = self._drop_client()
            self._stop.wait(interval)

    # -- reporting -------------------------------------------------------

    def _say(self, level: str, text: str) -> None:
        entry = self.log.add(level, text)
        if entry is not None:
            self._emit("log", {"level": level, "text": text})

    def _publish(self, status: StatusView) -> None:
        self._status = status
        self._emit("status", {"status": status})

    # -- connection ------------------------------------------------------

    def _discover(self) -> LcuClient:
        credentials = discover(self._install_dir)
        client = LcuClient(credentials)
        gameflow.read(client)  # proves the credentials before we trust them
        self._install_dir = credentials.install_dir or self._install_dir
        return client

    def _connect(self) -> float:
        try:
            client = self._connect_client()
        except ClientUnavailable:
            # A stale lockfile from a crashed client would keep failing, so the
            # cached install directory is dropped and discovery starts over.
            self._install_dir = None
            self._publish(StatusView())
            return INTERVAL_DISCONNECTED

        self._client = client
        self._reset_draft_cache()
        self._say(logbook.OK, "League client connected")

        if self.catalog.refresh_from_client(client):
            self._say(logbook.DEBUG, f"Champion list from client: {len(self.catalog)} champions")
            self._emit("catalog", {})

        summoner = client.current_summoner()
        if isinstance(summoner, dict):
            self._summoner = str(summoner.get("gameName") or summoner.get("displayName") or "")
        return 0.0

    def _drop_client(self) -> float:
        if self._client is not None:
            self._say(logbook.WARN, "Lost the League client, reconnecting")
        self._client = None
        self._summoner = ""
        self._reset_draft_cache()
        self.machine.decide(Snapshot(now=time.monotonic()), self.settings)
        self._publish(StatusView())
        return INTERVAL_DISCONNECTED

    def _reset_draft_cache(self) -> None:
        self._pickable = None
        self._pickable_at = 0.0
        self._chat_conversation = None
        self._chat_lookup_at = 0.0
        self._draft_identity = ""

    # -- the loop --------------------------------------------------------

    def _tick(self) -> float:
        if self._client is None:
            return self._connect()

        now = time.monotonic()
        snapshot = self._snapshot(now)
        previous_state = self.machine.state
        decision = self.machine.decide(snapshot, self.active_settings)

        if decision.state != previous_state:
            self._say(logbook.DEBUG, f"State: {previous_state.value} -> {decision.state.value}")
            if decision.state == AppState.CHAMP_SELECT:
                self._say(logbook.INFO, "Champion select started")

        for intent in decision.intents:
            succeeded = self._execute(intent)
            self.machine.record_result(intent, succeeded, time.monotonic())

        self._publish(
            StatusView(
                connected=True,
                state=decision.state.value,
                phase=snapshot.phase,
                phase_label=gameflow.label(snapshot.phase),
                detail=decision.detail,
                problem=decision.problem,
                turn=decision.turn,
                time_left=snapshot.session.time_left if snapshot.session else 0.0,
                accept_in=decision.countdown,
                in_draft=snapshot.session is not None,
                chat_sent=self.machine.chat_sent,
                chat_failed=self.machine.chat_failed,
                declared_champion=self.machine.declared_champion,
                summoner=self._summoner,
            )
        )
        self._serve_one_portrait()
        return self._interval(snapshot)

    def _interval(self, snapshot: Snapshot) -> float:
        if snapshot.session is not None:
            return INTERVAL_DRAFT
        if snapshot.phase in gameflow.QUEUE_PHASES:
            return INTERVAL_QUEUE
        return INTERVAL_IDLE

    def _snapshot(self, now: float) -> Snapshot:
        client = self._client
        phase = gameflow.read(client)

        ready_check = matchmaking.read(client) if phase in gameflow.QUEUE_PHASES else None
        session = cs.read(client) if phase == gameflow.CHAMP_SELECT else None

        if session is None:
            if self._draft_identity:
                self._reset_draft_cache()
            return Snapshot(now=now, connected=True, phase=phase, ready_check=ready_check)

        if session.identity != self._draft_identity:
            self._reset_draft_cache()
            self._draft_identity = session.identity

        if now - self._pickable_at >= PICKABLE_REFRESH:
            self._pickable = cs.pickable_ids(client)
            self._pickable_at = now

        return Snapshot(
            now=now,
            connected=True,
            phase=phase,
            ready_check=ready_check,
            session=session,
            pickable=self._pickable,
            chat_ready=self._chat_ready(now),
        )

    def _chat_ready(self, now: float) -> bool:
        """Resolve the draft chat room, at most once a second."""
        settings = self.active_settings
        if self._chat_conversation:
            return True
        if not settings.chat_enabled or not (settings.chat_message or "").strip():
            return False
        if self.machine.chat_sent or now - self._chat_lookup_at < CHAT_LOOKUP_INTERVAL:
            return False
        self._chat_lookup_at = now
        self._chat_conversation = chat.champ_select_conversation_id(self._client)
        return self._chat_conversation is not None

    # -- doing the thing -------------------------------------------------

    def _execute(self, intent: Intent) -> bool:
        client = self._client
        if client is None:
            return False

        if intent.kind == IntentKind.ACCEPT_READY_CHECK:
            if matchmaking.accept(client):
                self.settings.accepted_total += 1
                self._say(logbook.OK, "Queue accepted")
                self._emit("action", {"text": "Queue accepted", "level": logbook.OK, "chime": True})
                self._emit("counters", {})
                return True
            self._say(logbook.WARN, "The client refused the accept")
            return False

        if intent.kind == IntentKind.DECLARE_CHAMPION:
            name = self.catalog.name_of(intent.champion_id) or intent.champion_id
            if cs.declare(client, intent.action_id, intent.champion_id):
                self._say(logbook.OK, f"Champion declared: {name}")
                self._emit("action", {"text": f"Declared {name}", "level": logbook.OK})
                return True
            self._say(logbook.WARN, f"Could not declare {name}")
            return False

        if intent.kind == IntentKind.LOCK_CHAMPION:
            name = self.catalog.name_of(intent.champion_id) or intent.champion_id
            if cs.lock(client, intent.action_id, intent.champion_id):
                self.settings.picks_total += 1
                self._say(logbook.OK, f"Champion locked in: {name}")
                self._emit("action", {"text": f"Locked in {name}", "level": logbook.OK})
                self._emit("counters", {})
                return True
            self._say(logbook.WARN, f"Could not lock in {name}")
            return False

        if intent.kind == IntentKind.SEND_CHAT:
            if not self._chat_conversation:
                return False
            if chat.send(client, self._chat_conversation, intent.message):
                self._say(logbook.OK, "Draft message sent")
                self._emit("action", {"text": "Draft message sent", "level": logbook.OK})
                return True
            self._say(logbook.WARN, "Could not send the draft message")
            return False

        return False


def status_with(status: StatusView, **changes) -> StatusView:
    return replace(status, **changes)
