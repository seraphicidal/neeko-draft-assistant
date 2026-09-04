"""A stand-in League client, and builders for the payloads it serves.

A real draft lasts under a minute, cannot be summoned on demand and cannot be
rewound, so every draft test in this suite runs against these.
"""

from __future__ import annotations

from league.lcu_client import ClientUnavailable


class FakeLcu:
    """Answers the handful of routes the app uses, and records every call.

    Routes are keyed by ``(method, path)`` or just ``path``, and map to either a
    ``(status, body)`` pair or a callable taking the request payload.
    """

    def __init__(self, routes: dict | None = None) -> None:
        self.routes = dict(routes or {})
        self.calls: list[tuple[str, str, object]] = []
        self.unavailable = False

    # -- the client interface -------------------------------------------

    def request(self, method: str, path: str, payload=None, timeout: float = 4.0):
        if self.unavailable:
            raise ClientUnavailable("fake client is down")
        self.calls.append((method, path, payload))
        handler = self.routes.get((method, path), self.routes.get(path))
        if handler is None:
            return 404, {"httpStatus": 404, "message": "no such route in the fake"}
        if callable(handler):
            return handler(payload)
        return handler

    def get(self, path: str, timeout: float = 4.0):
        return self.request("GET", path, timeout=timeout)

    def post(self, path: str, payload=None, timeout: float = 4.0):
        return self.request("POST", path, payload, timeout)

    def patch(self, path: str, payload=None, timeout: float = 4.0):
        return self.request("PATCH", path, payload, timeout)

    def get_bytes(self, path: str, timeout: float = 8.0):
        status, body = self.request("GET", path, timeout=timeout)
        return body if 200 <= status < 300 else None

    def current_summoner(self):
        status, body = self.get("/lol-summoner/v1/current-summoner")
        return body if status == 200 else None

    # -- test helpers ----------------------------------------------------

    def paths(self, method: str | None = None) -> list[str]:
        return [path for verb, path, _ in self.calls if method is None or verb == method]

    def payloads(self, method: str, path_fragment: str) -> list[object]:
        return [
            payload
            for verb, path, payload in self.calls
            if verb == method and path_fragment in path
        ]

    def count(self, method: str, path_fragment: str) -> int:
        return len(self.payloads(method, path_fragment))


# -- payload builders ----------------------------------------------------


def action(
    action_id: int,
    cell: int,
    *,
    kind: str = "pick",
    champion: int = 0,
    completed: bool = False,
    in_progress: bool = False,
    ally: bool = True,
) -> dict:
    return {
        "id": action_id,
        "actorCellId": cell,
        "championId": champion,
        "completed": completed,
        "isInProgress": in_progress,
        "isAllyAction": ally,
        "pickTurn": action_id,
        "type": kind,
    }


def session_payload(
    *,
    local_cell: int = 0,
    actions: list[list[dict]] | None = None,
    phase: str = "BAN_PICK",
    time_left_ms: int = 27000,
    pick_intent: int = 0,
    chat_id: str = "draft-room-1",
) -> dict:
    return {
        "localPlayerCellId": local_cell,
        "actions": actions if actions is not None else [[action(1, local_cell)]],
        "timer": {"adjustedTimeLeftInPhase": time_left_ms, "phase": phase, "isInfinite": False},
        "myTeam": [{"cellId": local_cell, "championId": 0, "championPickIntent": pick_intent}],
        "theirTeam": [],
        "chatDetails": {"multiUserChatId": chat_id},
    }


def ready_check_payload(response: str = "None", state: str = "InProgress") -> dict:
    return {
        "state": state,
        "playerResponse": response,
        "timer": 1.0,
        "declinerIds": [],
        "dodgeWarning": "None",
    }


def conversations_payload(champ_select_id: str = "draft-room-1@sec.pvp.net") -> list[dict]:
    return [
        {"id": "club-room@sec.pvp.net", "type": "club"},
        {"id": champ_select_id, "type": "championSelect"},
    ]


class FakeSettings:
    """The attributes the state machine reads, and nothing else."""

    def __init__(self, **overrides) -> None:
        self.auto_accept = True
        self.accept_delay = 0.0
        self.auto_declare = True
        self.auto_pick = True
        self.preferred_champion_id = 0
        self.backup_champion_id = 0
        self.chat_enabled = False
        self.chat_message = ""
        for key, value in overrides.items():
            setattr(self, key, value)
