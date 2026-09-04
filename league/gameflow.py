"""Where the player is right now, straight from the client."""

from __future__ import annotations

from .lcu_client import LcuClient

ENDPOINT = "/lol-gameflow/v1/gameflow-phase"

# The phases the client reports. Anything unknown is passed through untouched
# so a new Riot phase shows up in the UI rather than being swallowed.
NONE = "None"
LOBBY = "Lobby"
MATCHMAKING = "Matchmaking"
READY_CHECK = "ReadyCheck"
CHAMP_SELECT = "ChampSelect"
GAME_START = "GameStart"
IN_PROGRESS = "InProgress"

LABELS = {
    NONE: "Idle in client",
    LOBBY: "In lobby",
    MATCHMAKING: "In queue",
    READY_CHECK: "Match found",
    "CheckedIntoTournament": "In tournament queue",
    CHAMP_SELECT: "Champion select",
    GAME_START: "Game starting",
    IN_PROGRESS: "In game",
    "Reconnect": "Reconnecting",
    "WaitingForStats": "Waiting for stats",
    "PreEndOfGame": "Post-game",
    "EndOfGame": "Post-game",
    "TerminatedInError": "Client error",
    "Unknown": "Unknown",
}

# Phases where a queue pop can happen, so polling tightens up.
QUEUE_PHASES = frozenset({MATCHMAKING, READY_CHECK, "CheckedIntoTournament"})


def label(phase: str) -> str:
    return LABELS.get(phase, phase)


def read(client: LcuClient) -> str:
    """The current phase, or ``Unknown`` if the client answered with nonsense."""
    _, body = client.get(ENDPOINT)
    return body if isinstance(body, str) else "Unknown"
