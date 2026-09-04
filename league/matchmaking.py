"""The queue pop: reading it, and pressing ACCEPT.

Unchanged in behaviour from the original auto-accept build -- only the home of
the code moved.
"""

from __future__ import annotations

from dataclasses import dataclass

from .lcu_client import LcuClient, ok

READY_CHECK = "/lol-matchmaking/v1/ready-check"
ACCEPT = "/lol-matchmaking/v1/ready-check/accept"

# playerResponse values
NO_ANSWER = "None"
ACCEPTED = "Accepted"
DECLINED = "Declined"


@dataclass(frozen=True)
class ReadyCheck:
    state: str            # InProgress once the popup is up
    player_response: str  # None / Accepted / Declined
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
    """The live queue pop, or None when there is no match to answer."""
    status, body = client.get(READY_CHECK)
    if status != 200 or not isinstance(body, dict):
        return None
    return ReadyCheck.parse(body)


def accept(client: LcuClient) -> bool:
    status, _ = client.post(ACCEPT)
    return ok(status)
