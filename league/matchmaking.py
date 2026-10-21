
from __future__ import annotations

from dataclasses import dataclass

from .lcu_client import LcuClient, ok

READY_CHECK = "/lol-matchmaking/v1/ready-check"
ACCEPT = "/lol-matchmaking/v1/ready-check/accept"

NO_ANSWER = "None"
ACCEPTED = "Accepted"
DECLINED = "Declined"


@dataclass(frozen=True)
class ReadyCheck:
    state: str
    player_response: str
    timer: float

    @property
    def is_live(self) -> bool:
        return self.state == "InProgress"

    @property
    def is_unanswered(self) -> bool:
        return self.is_live and self.player_response == NO_ANSWER

    @classmethod
    def parse(cls, body: dict) -> "ReadyCheck":
        return cls(
            state=str(body.get("state", "")),
            player_response=str(body.get("playerResponse", NO_ANSWER)),
            timer=float(body.get("timer") or 0.0),
        )


def read(client: LcuClient) -> ReadyCheck | None:
    status, body = client.get(READY_CHECK)
    if status != 200 or not isinstance(body, dict):
        return None
    return ReadyCheck.parse(body)


def accept(client: LcuClient) -> bool:
    status, _ = client.post(ACCEPT)
    return ok(status)
