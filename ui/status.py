"""What each app state looks like, in words and colour.

The state machine decides; this turns its decision into presentation: a label
for the pill, a headline for the stage, a supporting line, the colour, which
Neeko illustration fits, and which scene the dashboard should show.

No Qt in here on purpose -- it is plain data and therefore testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from ui import theme

# Scenes the dashboard can show. One per situation, not one per state.
OFFLINE = "offline"
IDLE = "idle"
QUEUE = "queue"
READY = "ready"
DRAFT = "draft"
GAME = "game"

# Illustration roles, resolved to files by ui.assets.
ART_IDLE = "mood_idle"
ART_HAPPY = "mood_happy"
ART_ALERT = "mood_alert"
ART_CALM = "mood_calm"
ART_PORTRAIT = "portrait"


@dataclass(frozen=True)
class Status:
    """Everything the interface needs to describe one moment."""

    label: str        # short, for the pill and the tray
    headline: str     # the stage's own heading
    detail: str       # one supporting sentence
    voice: str        # what Neeko says
    tone: str         # colour from the palette
    art: str          # illustration role
    scene: str        # which stage to show
    live: bool = True  # whether the status dot should breathe


_UNKNOWN = Status(
    label="Waiting",
    headline="Waiting for League",
    detail="Neeko will wake up as soon as the client is open.",
    voice="Neeko is waiting...",
    tone=theme.TEXT_MUTED,
    art=ART_IDLE,
    scene=OFFLINE,
    live=False,
)

BY_STATE = {
    "DISCONNECTED": Status(
        label="League offline",
        headline="Waiting for League",
        detail="Open League of Legends and Neeko will connect on her own.",
        voice="Neeko is waiting for League...",
        tone=theme.TEXT_MUTED,
        art=ART_IDLE,
        scene=OFFLINE,
        live=False,
    ),
    "WAITING": Status(
        label="League connected",
        headline="Ready for your next game",
        detail="Neeko is watching the client. Queue up whenever you like.",
        voice="Neeko is ready when you are.",
        tone=theme.BLUE,
        art=ART_HAPPY,
        scene=IDLE,
    ),
    "LOBBY": Status(
        label="In lobby",
        headline="Ready for your next game",
        detail="Neeko will answer the queue the moment it pops.",
        voice="Neeko likes this lobby.",
        tone=theme.BLUE,
        art=ART_HAPPY,
        scene=IDLE,
    ),
    "QUEUED": Status(
        label="Searching",
        headline="Searching for a match",
        detail="Neeko is watching the queue for you.",
        voice="Neeko is watching the queue...",
        tone=theme.BLUE,
        art=ART_IDLE,
        scene=QUEUE,
    ),
    "READY_CHECK": Status(
        label="Match found",
        headline="Match found",
        detail="Accepting automatically.",
        voice="Match found! Neeko is on it.",
        tone=theme.ACCENT,
        art=ART_ALERT,
        scene=READY,
    ),
    "ACCEPTED": Status(
        label="Accepted",
        headline="Match accepted",
        detail="See you in champion select.",
        voice="Neeko accepted the match!",
        tone=theme.SUCCESS,
        art=ART_HAPPY,
        scene=READY,
    ),
    "CHAMP_SELECT": Status(
        label="Champion select",
        headline="Champion select",
        detail="Neeko is watching the draft.",
        voice="Neeko is watching the draft...",
        tone=theme.BLUE,
        art=ART_PORTRAIT,
        scene=DRAFT,
    ),
    "WAITING_FOR_MY_TURN": Status(
        label="Champion select",
        headline="Waiting for your turn",
        detail="Neeko will step in the moment the pick is yours.",
        voice="Neeko is waiting for your turn...",
        tone=theme.BLUE,
        art=ART_PORTRAIT,
        scene=DRAFT,
    ),
    "MY_TURN": Status(
        label="Your turn",
        headline="It's your turn",
        detail="Neeko is picking for you now.",
        voice="It's your turn!",
        tone=theme.ACCENT,
        art=ART_ALERT,
        scene=DRAFT,
    ),
    "LOCKED": Status(
        label="Locked in",
        headline="Locked in",
        detail="Nothing left to do. Good luck out there.",
        voice="Locked in. Good luck!",
        tone=theme.SUCCESS,
        art=ART_CALM,
        scene=DRAFT,
    ),
    "IN_GAME": Status(
        label="In game",
        headline="In game",
        detail="Have fun. Neeko will be here when you get back.",
        voice="Neeko is cheering from here.",
        tone=theme.BLUE,
        art=ART_CALM,
        scene=GAME,
        live=False,
    ),
    "POST_GAME": Status(
        label="Post-game",
        headline="Nice one",
        detail="Neeko is ready whenever you want another.",
        voice="Neeko hopes that went well.",
        tone=theme.TEXT_SECONDARY,
        art=ART_HAPPY,
        scene=IDLE,
        live=False,
    ),
}


def for_state(state: str) -> Status:
    return BY_STATE.get(state, _UNKNOWN)


@dataclass(frozen=True)
class Reaction:
    """A short-lived thing Neeko says after the app did something."""

    voice: str
    tone: str


REACTION_SECONDS = 4.0

_REACTIONS = {
    "Queue accepted": Reaction("Neeko accepted the match!", theme.SUCCESS),
    "Draft message sent": Reaction("Message sent!", theme.BLUE),
}


def for_action(text: str) -> Reaction | None:
    """The reaction to something the app just did, if it deserves one."""
    if text in _REACTIONS:
        return _REACTIONS[text]
    if text.startswith("Declared "):
        return Reaction(f"Neeko hovered {text[len('Declared '):]}!", theme.ACCENT)
    if text.startswith("Locked in "):
        return Reaction(f"{text[len('Locked in '):]} locked in!", theme.SUCCESS)
    return None


# Anything the user should never have to decode. The watcher and the state
# machine already speak plainly; this catches the few phrasings that leak.
_REWRITES = {
    "Lost the League client, reconnecting": (
        "Lost the League client. Neeko is reconnecting..."
    ),
    "The client refused the accept. Press it yourself.": (
        "League would not accept the match. Please press Accept yourself."
    ),
    "Could not declare the champion.": (
        "Couldn't hover your champion. League may not allow it in this queue."
    ),
    "Could not lock the champion in.": (
        "Couldn't lock your champion in. Please pick it yourself."
    ),
    "Could not send the draft message.": (
        "Couldn't send the draft message. Chat may not be ready yet."
    ),
}


def humanise(problem: str) -> str:
    """A message a player can act on, never an endpoint or a status code."""
    if not problem:
        return ""
    return _REWRITES.get(problem, problem)
