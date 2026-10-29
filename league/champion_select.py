
from __future__ import annotations

from dataclasses import dataclass, field

from .lcu_client import LcuClient, ok

SESSION = "/lol-champ-select/v1/session"
ACTION = "/lol-champ-select/v1/session/actions/{action_id}"
PICKABLE = "/lol-champ-select/v1/pickable-champion-ids"
BANNABLE = "/lol-champ-select/v1/bannable-champion-ids"

PLANNING = "PLANNING"
BAN_PICK = "BAN_PICK"
FINALIZATION = "FINALIZATION"

PICK = "pick"
BAN = "ban"


@dataclass(frozen=True)
class Action:
    id: int
    actor_cell_id: int
    champion_id: int
    completed: bool
    in_progress: bool
    type: str
    is_ally: bool

    @classmethod
    def parse(cls, raw: dict) -> "Action":
        return cls(
            id=int(raw.get("id", -1)),
            actor_cell_id=int(raw.get("actorCellId", -1)),
            champion_id=int(raw.get("championId") or 0),
            completed=bool(raw.get("completed")),
            in_progress=bool(raw.get("isInProgress")),
            type=str(raw.get("type", "")),
            is_ally=bool(raw.get("isAllyAction", True)),
        )


@dataclass(frozen=True)
class Session:
    local_cell_id: int
    actions: tuple[Action, ...]
    phase: str
    time_left: float
    pick_intent: int
    chat_id: str
    identity: str = field(compare=False, default="")
    assigned_position: str = ""
    ally_hovered: frozenset[int] = frozenset()

    @property
    def my_pick_action(self) -> Action | None:
        return self._mine(PICK)

    @property
    def my_ban_action(self) -> Action | None:
        return self._mine(BAN)

    def _mine(self, kind: str) -> Action | None:
        for action in self.actions:
            if action.actor_cell_id == self.local_cell_id and action.type == kind:
                if not action.completed:
                    return action
        return None

    @property
    def is_my_pick_turn(self) -> bool:
        action = self.my_pick_action
        return bool(action and action.in_progress and not action.completed)

    @property
    def is_my_ban_turn(self) -> bool:
        action = self.my_ban_action
        return bool(action and action.in_progress and not action.completed)

    @property
    def has_locked(self) -> bool:
        return any(
            action.actor_cell_id == self.local_cell_id
            and action.type == PICK
            and action.completed
            for action in self.actions
        )

    @property
    def taken_champion_ids(self) -> frozenset[int]:
        taken = set()
        for action in self.actions:
            if action.champion_id <= 0:
                continue
            if action.type == BAN and action.completed:
                taken.add(action.champion_id)
            elif action.type == PICK and action.completed:
                if action.actor_cell_id != self.local_cell_id:
                    taken.add(action.champion_id)
        return frozenset(taken)

    @classmethod
    def parse(cls, raw: dict) -> "Session":
        local_cell_id = int(raw.get("localPlayerCellId", -1))

        actions: list[Action] = []
        for group in raw.get("actions") or []:
            if not isinstance(group, list):
                continue
            actions.extend(Action.parse(entry) for entry in group if isinstance(entry, dict))

        timer = raw.get("timer") or {}
        time_left = max(0.0, float(timer.get("adjustedTimeLeftInPhase") or 0.0) / 1000.0)

        pick_intent = 0
        assigned_position = ""
        ally_hovered = set()
        for member in raw.get("myTeam") or []:
            if not isinstance(member, dict):
                continue
            cell_id = int(member.get("cellId", -1))
            intent = int(member.get("championPickIntent") or 0)
            if cell_id == local_cell_id:
                pick_intent = intent
                assigned_position = str(
                    member.get("assignedPosition") or member.get("selectedPosition") or ""
                ).lower()
            elif intent > 0:
                ally_hovered.add(intent)

        chat_id = str((raw.get("chatDetails") or {}).get("multiUserChatId") or "")

        identity = chat_id or f"cell{local_cell_id}:" + ",".join(
            str(action.id) for action in actions
        )

        return cls(
            local_cell_id=local_cell_id,
            actions=tuple(actions),
            phase=str(timer.get("phase") or ""),
            time_left=time_left,
            pick_intent=pick_intent,
            chat_id=chat_id,
            identity=identity,
            assigned_position=assigned_position,
            ally_hovered=frozenset(ally_hovered),
        )


def read(client: LcuClient) -> Session | None:
    status, body = client.get(SESSION)
    if status != 200 or not isinstance(body, dict):
        return None
    return Session.parse(body)


def pickable_ids(client: LcuClient) -> frozenset[int] | None:
    status, body = client.get(PICKABLE)
    if status != 200 or not isinstance(body, list):
        return None
    return frozenset(int(champion_id) for champion_id in body)


def declare(client: LcuClient, action_id: int, champion_id: int) -> bool:
    status, _ = client.patch(ACTION.format(action_id=action_id), {"championId": champion_id})
    return ok(status)


def lock(client: LcuClient, action_id: int, champion_id: int) -> bool:
    status, _ = client.patch(
        ACTION.format(action_id=action_id), {"championId": champion_id, "completed": True}
    )
    return ok(status)


def ban(client: LcuClient, action_id: int, champion_id: int) -> bool:
    status, _ = client.patch(
        ACTION.format(action_id=action_id), {"championId": champion_id, "completed": True}
    )
    return ok(status)
