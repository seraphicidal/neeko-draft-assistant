"""Neeko's reactions.

She is the app's voice: one short line that follows what the client is doing,
plus the colour everything else picks up. Reactions to events (a queue answered,
a champion hovered) briefly take over, then she settles back into the state.
"""

from __future__ import annotations

from dataclasses import dataclass

from ui import theme

REACTION_SECONDS = 4.0


@dataclass(frozen=True)
class Mood:
    line: str
    colour: str
    energy: float = 0.0   # 0 calm, 1 excited -- drives the glow and the bounce


IDLE = Mood("Neeko is waiting for League...", theme.DIM)

BY_STATE = {
    "DISCONNECTED": IDLE,
    "WAITING": Mood("Neeko is ready when you are.", theme.SKY, 0.1),
    "LOBBY": Mood("Neeko likes this lobby.", theme.SKY, 0.2),
    "QUEUED": Mood("Neeko is watching the queue...", theme.SKY_BRIGHT, 0.35),
    "READY_CHECK": Mood("Match found! Neeko is on it.", theme.ORANGE, 0.9),
    "ACCEPTED": Mood("Neeko accepted the match!", theme.SUCCESS, 0.7),
    "CHAMP_SELECT": Mood("Neeko is watching the draft...", theme.SKY_BRIGHT, 0.4),
    "WAITING_FOR_MY_TURN": Mood("Neeko is waiting for your turn...", theme.SKY, 0.3),
    "MY_TURN": Mood("It's your turn!", theme.ORANGE, 1.0),
    "LOCKED": Mood("Locked in. Good luck out there!", theme.SUCCESS, 0.5),
    "IN_GAME": Mood("Neeko is cheering from here.", theme.CYAN, 0.2),
    "POST_GAME": Mood("Neeko hopes that went well.", theme.MUTED, 0.1),
}

# Short-lived reactions, keyed by the text the watcher reports.
REACTIONS = {
    "Queue accepted": Mood("Neeko accepted the match!", theme.SUCCESS, 1.0),
    "Draft message sent": Mood("Message sent!", theme.SKY_BRIGHT, 0.6),
}

DECLARED = Mood("Neeko found your champion!", theme.ORANGE, 0.9)
LOCKED_IN = Mood("Locked in!", theme.SUCCESS, 1.0)
WORRIED = Mood("Neeko is not sure about this one...", theme.WARNING, 0.4)


def for_state(state: str) -> Mood:
    return BY_STATE.get(state, IDLE)


def for_action(text: str) -> Mood | None:
    """The reaction to something the app just did, if it deserves one."""
    if text in REACTIONS:
        return REACTIONS[text]
    if text.startswith("Declared "):
        return Mood(f"Neeko found your champion! {text[9:]} it is.", theme.ORANGE, 0.9)
    if text.startswith("Locked in "):
        return Mood(f"{text[10:]} locked in!", theme.SUCCESS, 1.0)
    return None
