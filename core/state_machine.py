"""What the assistant is looking at, and what -- if anything -- it should do.

This module makes every decision and performs none of them. It takes a snapshot
of the client and hands back a state plus zero or more intents; the watcher does
the talking. That split is what makes the draft logic testable without a real
champion select, and it is where all the failsafes live:

* nothing happens unless the client actually says it is our turn
* an unavailable champion is never swapped for a random one
* every action is attempted a bounded number of times, with backoff
* a chat message, a hover and an accept happen once per lobby, never twice
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from league import champion_select as cs
from league import matchmaking as mm
from league import gameflow

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (1.0, 2.0, 4.0)


class AppState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    WAITING = "WAITING"
    LOBBY = "LOBBY"
    QUEUED = "QUEUED"
    READY_CHECK = "READY_CHECK"
    ACCEPTED = "ACCEPTED"
    CHAMP_SELECT = "CHAMP_SELECT"
    WAITING_FOR_MY_TURN = "WAITING_FOR_MY_TURN"
    MY_TURN = "MY_TURN"
    LOCKED = "LOCKED"
    IN_GAME = "IN_GAME"
    POST_GAME = "POST_GAME"


class IntentKind(str, Enum):
    ACCEPT_READY_CHECK = "ACCEPT_READY_CHECK"
    DECLARE_CHAMPION = "DECLARE_CHAMPION"
    LOCK_CHAMPION = "LOCK_CHAMPION"
    SEND_CHAT = "SEND_CHAT"


@dataclass(frozen=True)
class Intent:
    kind: IntentKind
    champion_id: int = 0
    action_id: int = 0
    message: str = ""


@dataclass(frozen=True)
class Snapshot:
    """Everything the machine is allowed to know."""

    now: float
    connected: bool = False
    phase: str = "Unknown"
    ready_check: mm.ReadyCheck | None = None
    session: cs.Session | None = None
    pickable: frozenset[int] | None = None
    chat_ready: bool = False


@dataclass(frozen=True)
class Decision:
    state: AppState
    intents: tuple[Intent, ...] = ()
    detail: str = ""
    problem: str = ""
    turn: str = ""
    countdown: float = 0.0   # seconds left before the accept fires


@dataclass
class _Attempts:
    count: int = 0
    next_allowed_at: float = 0.0
    done: bool = False
    exhausted: bool = False

    def allow(self, now: float) -> bool:
        return not self.done and not self.exhausted and now >= self.next_allowed_at

    def succeeded(self) -> None:
        self.done = True

    def failed(self, now: float) -> None:
        self.count += 1
        if self.count >= MAX_ATTEMPTS:
            self.exhausted = True
            return
        self.next_allowed_at = now + BACKOFF_SECONDS[min(self.count, len(BACKOFF_SECONDS)) - 1]


PHASE_STATES = {
    gameflow.LOBBY: AppState.LOBBY,
    gameflow.MATCHMAKING: AppState.QUEUED,
    gameflow.IN_PROGRESS: AppState.IN_GAME,
    gameflow.GAME_START: AppState.IN_GAME,
    "Reconnect": AppState.IN_GAME,
    "WaitingForStats": AppState.POST_GAME,
    "PreEndOfGame": AppState.POST_GAME,
    "EndOfGame": AppState.POST_GAME,
}


class StateMachine:
    """Stateful only in what it must remember: what has already been done."""

    def __init__(self) -> None:
        self.state = AppState.DISCONNECTED
        self._pop_seen_at: float | None = None
        self._session_identity = ""
        self._declared_champion = 0
        self._attempts: dict[IntentKind, _Attempts] = {}
        self._reset_queue()
        self._reset_draft("")

    # -- bookkeeping -----------------------------------------------------

    def _attempt(self, kind: IntentKind) -> _Attempts:
        return self._attempts.setdefault(kind, _Attempts())

    def _reset_queue(self) -> None:
        self._pop_seen_at = None
        self._attempts[IntentKind.ACCEPT_READY_CHECK] = _Attempts()

    def _reset_draft(self, identity: str) -> None:
        self._session_identity = identity
        self._declared_champion = 0
        for kind in (IntentKind.DECLARE_CHAMPION, IntentKind.LOCK_CHAMPION, IntentKind.SEND_CHAT):
            self._attempts[kind] = _Attempts()

    def record_result(self, intent: Intent, succeeded: bool, now: float) -> None:
        """Told by the watcher how an intent actually went."""
        attempt = self._attempt(intent.kind)
        if succeeded:
            attempt.succeeded()
            if intent.kind == IntentKind.DECLARE_CHAMPION:
                self._declared_champion = intent.champion_id
        else:
            attempt.failed(now)

    @property
    def chat_sent(self) -> bool:
        return self._attempt(IntentKind.SEND_CHAT).done

    @property
    def chat_failed(self) -> bool:
        return self._attempt(IntentKind.SEND_CHAT).exhausted

    @property
    def declared_champion(self) -> int:
        return self._declared_champion

    # -- the decision ----------------------------------------------------

    def decide(self, snapshot: Snapshot, settings) -> Decision:
        decision = self._decide(snapshot, settings)
        self.state = decision.state
        return decision

    def _decide(self, snapshot: Snapshot, settings) -> Decision:
        if not snapshot.connected:
            self._reset_queue()
            self._reset_draft("")
            return Decision(AppState.DISCONNECTED, detail="Waiting for League Client...")

        if snapshot.ready_check is not None:
            return self._decide_queue(snapshot, settings)
        self._reset_queue()

        if snapshot.session is not None:
            return self._decide_draft(snapshot, settings)
        if self._session_identity:
            self._reset_draft("")

        state = PHASE_STATES.get(snapshot.phase, AppState.WAITING)
        return Decision(state, detail=gameflow.label(snapshot.phase))

    # -- queue -----------------------------------------------------------

    def _decide_queue(self, snapshot: Snapshot, settings) -> Decision:
        pop = snapshot.ready_check
        if not pop.is_live:
            return Decision(AppState.READY_CHECK, detail="Match found")

        if pop.player_response == mm.ACCEPTED:
            return Decision(AppState.ACCEPTED, detail="Match accepted")
        if pop.player_response == mm.DECLINED:
            return Decision(AppState.ACCEPTED, detail="Match declined")

        if self._pop_seen_at is None:
            self._pop_seen_at = snapshot.now

        if not settings.auto_accept:
            return Decision(AppState.READY_CHECK, detail="Match found - auto accept is off")

        attempt = self._attempt(IntentKind.ACCEPT_READY_CHECK)
        if attempt.exhausted:
            return Decision(
                AppState.READY_CHECK,
                detail="Match found",
                problem="The client refused the accept. Press it yourself.",
            )

        waited = snapshot.now - self._pop_seen_at
        remaining = settings.accept_delay - waited
        if remaining > 0:
            return Decision(
                AppState.READY_CHECK,
                detail=f"Accepting in {remaining:.1f}s",
                countdown=remaining,
            )
        if not attempt.allow(snapshot.now):
            return Decision(AppState.READY_CHECK, detail="Accepting...")

        return Decision(
            AppState.READY_CHECK,
            intents=(Intent(IntentKind.ACCEPT_READY_CHECK),),
            detail="Accepting...",
        )

    # -- draft -----------------------------------------------------------

    def _decide_draft(self, snapshot: Snapshot, settings) -> Decision:
        session = snapshot.session
        if session.identity != self._session_identity:
            self._reset_draft(session.identity)

        intents: list[Intent] = []
        problems: list[str] = []

        if session.has_locked:
            state, turn = AppState.LOCKED, ""
        elif session.is_my_pick_turn:
            state, turn = AppState.MY_TURN, "PICK"
        elif session.is_my_ban_turn:
            state, turn = AppState.MY_TURN, "BAN"
        elif session.phase == cs.PLANNING:
            state, turn = AppState.CHAMP_SELECT, "DECLARE"
        else:
            state, turn = AppState.WAITING_FOR_MY_TURN, ""

        intents.extend(self._chat_intents(snapshot, settings, problems))
        intents.extend(self._champion_intents(snapshot, settings, session, problems))

        detail = {
            AppState.LOCKED: "Champion locked in",
            AppState.MY_TURN: f"Your turn: {turn}",
            AppState.CHAMP_SELECT: "Declare phase",
            AppState.WAITING_FOR_MY_TURN: "Waiting for your turn",
        }[state]

        return Decision(
            state=state,
            intents=tuple(intents),
            detail=detail,
            problem=problems[0] if problems else "",
            turn=turn,
        )

    def _chat_intents(self, snapshot: Snapshot, settings, problems: list[str]) -> list[Intent]:
        message = (settings.chat_message or "").strip()
        if not settings.chat_enabled or not message:
            return []

        attempt = self._attempt(IntentKind.SEND_CHAT)
        if attempt.exhausted:
            problems.append("Could not send the draft message.")
            return []
        if not attempt.allow(snapshot.now) or not snapshot.chat_ready:
            return []
        return [Intent(IntentKind.SEND_CHAT, message=message)]

    def _champion_intents(
        self, snapshot: Snapshot, settings, session: cs.Session, problems: list[str]
    ) -> list[Intent]:
        if not (settings.auto_declare or settings.auto_pick):
            return []
        if session.has_locked:
            return []

        action = session.my_pick_action
        if action is None:
            return []  # no pick slot of ours in this lobby (spectator, or bans only)

        champion_id, problem = self._choose_champion(session, snapshot.pickable, settings)
        if not champion_id:
            if problem:
                problems.append(problem)
            return []

        intents: list[Intent] = []

        # Hovering is safe at any point in the draft: it only shows intent.
        if settings.auto_declare and self._declared_champion != champion_id:
            attempt = self._attempt(IntentKind.DECLARE_CHAMPION)
            if attempt.exhausted:
                problems.append("Could not declare the champion.")
            elif session.pick_intent == champion_id:
                self._declared_champion = champion_id  # already hovered by hand
            elif attempt.allow(snapshot.now):
                intents.append(
                    Intent(IntentKind.DECLARE_CHAMPION, champion_id, action.id)
                )

        # Locking in happens only when the client says the action is live.
        if settings.auto_pick and session.is_my_pick_turn:
            attempt = self._attempt(IntentKind.LOCK_CHAMPION)
            if attempt.exhausted:
                problems.append("Could not lock the champion in.")
            elif attempt.allow(snapshot.now):
                intents.append(Intent(IntentKind.LOCK_CHAMPION, champion_id, action.id))

        return intents

    def _choose_champion(self, session: cs.Session, pickable, settings) -> tuple[int, str]:
        """The preferred champion, the backup, or nothing at all.

        Never a substitute the user did not name: an assistant that picks a
        random champion because the wanted one is gone is worse than one that
        does nothing.
        """
        wanted = [
            ("Preferred", int(getattr(settings, "preferred_champion_id", 0) or 0)),
            ("Backup", int(getattr(settings, "backup_champion_id", 0) or 0)),
        ]
        if not any(champion_id for _, champion_id in wanted):
            return 0, "No champion picked yet."

        taken = session.taken_champion_ids
        blocked = ""
        for role, champion_id in wanted:
            if not champion_id:
                continue
            if champion_id in taken:
                blocked = blocked or f"{role} champion is banned or already taken."
                continue
            # An empty pickable set means the client would not say; only a
            # populated set is treated as authoritative.
            if pickable and champion_id not in pickable:
                blocked = blocked or f"{role} champion is not available to pick."
                continue
            return champion_id, ""
        return 0, blocked or "No champion available."
