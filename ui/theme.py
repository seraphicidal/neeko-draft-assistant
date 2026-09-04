"""The design system: warm orange, light blue, deep navy.

Orange is the signature colour and marks anything the app is doing for you --
the chosen champion, primary actions, live highlights. Light blue carries state:
connection, secondary controls, calm information. Neeko's magenta and mint are
accents only, a few pixels at a time.

Widgets that need real shape are painted in `widgets.py`; this file is the token
list plus the stylesheet for the plain Qt controls.
"""

from __future__ import annotations

# -- ground ---------------------------------------------------------------
NAVY_900 = "#0A101C"   # window ground
NAVY_850 = "#0E1626"   # header base
NAVY_800 = "#121C30"   # panel
NAVY_750 = "#16233A"   # raised panel
NAVY_700 = "#1C2C47"   # control track
NAVY_600 = "#26395A"   # hover
LINE = "#1F3050"       # hairline separators

# -- orange, the signature ------------------------------------------------
ORANGE = "#FF8A3D"
ORANGE_DEEP = "#F2661C"
ORANGE_SOFT = "#FFB067"
PEACH = "#FFD6B0"

# -- light blue, the state colour ----------------------------------------
SKY = "#7DD3FC"
SKY_BRIGHT = "#38BDF8"
SKY_DEEP = "#0C87C4"
CYAN = "#67E8F9"

# -- neutrals -------------------------------------------------------------
CREAM = "#FFF7EC"
TEXT = "#EEF4FF"
MUTED = "#8FA6C4"
DIM = "#5A6E8C"

# -- semantics ------------------------------------------------------------
SUCCESS = "#3ED598"
WARNING = "#FFC861"
DANGER = "#FF6B6B"

# -- Neeko accents, used sparingly ---------------------------------------
NEEKO_PINK = "#E84AA8"
NEEKO_MINT = "#4FD8C8"

RADIUS = 18
PANEL_RADIUS = 14
CONTROL_RADIUS = 10

FONT = "Segoe UI"
MONO = "Consolas"

# What colour a given app state paints itself in.
STATE_COLOURS = {
    "DISCONNECTED": DIM,
    "WAITING": MUTED,
    "LOBBY": SKY,
    "QUEUED": SKY_BRIGHT,
    "READY_CHECK": ORANGE,
    "ACCEPTED": SUCCESS,
    "CHAMP_SELECT": SKY_BRIGHT,
    "WAITING_FOR_MY_TURN": SKY,
    "MY_TURN": ORANGE,
    "LOCKED": SUCCESS,
    "IN_GAME": CYAN,
    "POST_GAME": MUTED,
}

LEVEL_COLOURS = {
    "ok": SUCCESS,
    "info": TEXT,
    "warn": WARNING,
    "error": DANGER,
    "debug": DIM,
}


def rgba(hex_colour: str, alpha: float) -> str:
    """`#RRGGBB` plus an alpha, in the form Qt stylesheets want."""
    value = hex_colour.lstrip("#")
    red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {alpha:.3f})"


def stylesheet() -> str:
    return f"""
    QWidget {{
        color: {TEXT};
        font-family: "{FONT}";
        font-size: 13px;
    }}
    QWidget#root {{
        background: {NAVY_900};
        border: 1px solid {LINE};
        border-radius: {RADIUS}px;
    }}

    /* -- type scale -------------------------------------------------- */
    QLabel#display   {{ font-size: 19px; font-weight: 700; color: {CREAM}; }}
    QLabel#title     {{ font-size: 15px; font-weight: 700; color: {TEXT}; }}
    QLabel#caption   {{ font-size: 10px; font-weight: 700; letter-spacing: 2px;
                        color: {DIM}; }}
    QLabel#body      {{ font-size: 13px; color: {TEXT}; }}
    QLabel#muted     {{ font-size: 12px; color: {MUTED}; }}
    QLabel#small     {{ font-size: 11px; color: {DIM}; }}
    QLabel#accent    {{ font-size: 13px; font-weight: 600; color: {ORANGE}; }}
    QLabel#sky       {{ font-size: 12px; font-weight: 600; color: {SKY}; }}
    QLabel#warning   {{ font-size: 11px; color: {WARNING}; }}
    QLabel#danger    {{ font-size: 11px; color: {DANGER}; }}

    /* -- inputs ------------------------------------------------------- */
    QLineEdit {{
        background: {NAVY_750};
        border: 1px solid {LINE};
        border-radius: {CONTROL_RADIUS}px;
        padding: 8px 12px;
        color: {TEXT};
        selection-background-color: {ORANGE_DEEP};
    }}
    QLineEdit:hover  {{ border: 1px solid {NAVY_600}; }}
    QLineEdit:focus  {{ border: 1px solid {SKY_BRIGHT};
                        background: {NAVY_700}; }}

    /* -- buttons ------------------------------------------------------ */
    QPushButton {{
        background: {NAVY_700};
        border: 1px solid {LINE};
        border-radius: {CONTROL_RADIUS}px;
        padding: 8px 18px;
        color: {TEXT};
        font-weight: 600;
    }}
    QPushButton:hover   {{ background: {NAVY_600}; border: 1px solid {SKY_DEEP}; }}
    QPushButton:pressed {{ background: {NAVY_750}; }}
    QPushButton:disabled {{ color: {DIM}; border: 1px solid {LINE}; background: {NAVY_800}; }}

    QPushButton#primary {{
        background: {ORANGE};
        border: 1px solid {ORANGE};
        color: #26150A;
    }}
    QPushButton#primary:hover   {{ background: {ORANGE_SOFT}; border: 1px solid {ORANGE_SOFT}; }}
    QPushButton#primary:pressed {{ background: {ORANGE_DEEP}; }}

    QPushButton#quiet {{
        background: transparent;
        border: 1px solid {LINE};
        color: {MUTED};
    }}
    QPushButton#quiet:hover {{ color: {TEXT}; border: 1px solid {SKY_DEEP}; }}

    QPushButton#link {{
        background: transparent;
        border: none;
        color: {SKY};
        padding: 2px 4px;
        font-weight: 600;
    }}
    QPushButton#link:hover {{ color: {CYAN}; }}

    QPushButton#windowButton {{
        background: transparent;
        border: none;
        color: {MUTED};
        font-size: 14px;
        padding: 0px;
        border-radius: 6px;
    }}
    QPushButton#windowButton:hover {{ color: {CREAM}; background: {rgba(SKY, 0.16)}; }}
    QPushButton#windowButton[danger="true"]:hover {{ color: #2A0F0F; background: {DANGER}; }}

    /* -- champion results --------------------------------------------- */
    QListWidget {{
        background: {NAVY_750};
        border: 1px solid {SKY_DEEP};
        border-radius: {CONTROL_RADIUS}px;
        outline: none;
        padding: 5px;
    }}
    QListWidget::item {{
        padding: 6px 8px;
        border-radius: 8px;
        color: {TEXT};
    }}
    QListWidget::item:hover    {{ background: {NAVY_600}; }}
    QListWidget::item:selected {{ background: {rgba(ORANGE, 0.22)}; color: {CREAM}; }}

    /* -- log ----------------------------------------------------------- */
    QTextEdit {{
        background: {NAVY_900};
        border: 1px solid {LINE};
        border-radius: {CONTROL_RADIUS}px;
        font-family: "{MONO}", monospace;
        font-size: 11px;
        color: {MUTED};
    }}

    QComboBox {{
        background: {NAVY_750};
        border: 1px solid {LINE};
        border-radius: {CONTROL_RADIUS}px;
        padding: 6px 10px;
        color: {TEXT};
    }}
    QComboBox:hover {{ border: 1px solid {SKY_DEEP}; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {NAVY_750};
        border: 1px solid {SKY_DEEP};
        border-radius: 8px;
        selection-background-color: {rgba(ORANGE, 0.25)};
        color: {TEXT};
        padding: 4px;
    }}

    /* -- scrolling ------------------------------------------------------ */
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 9px; margin: 6px 3px 6px 0; }}
    QScrollBar::handle:vertical {{
        background: {NAVY_600};
        border-radius: 4px;
        min-height: 36px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {SKY_DEEP}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

    QToolTip {{
        background: {NAVY_750};
        color: {TEXT};
        border: 1px solid {SKY_DEEP};
        border-radius: 8px;
        padding: 6px 9px;
    }}

    QDialog {{ background: {NAVY_900}; }}
    """
