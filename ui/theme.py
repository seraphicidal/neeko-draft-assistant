"""The design system: tokens first, stylesheet second.

Every colour, size and duration in the app comes from here. Components take
tokens rather than literals, so the interface stays consistent and a change to
the palette is a change in one place.

Orange is the primary accent -- it marks what the app is doing for you and what
you have chosen. Light blue is the state colour: connection, information, calm
progress. Purple appears only as a small nod to Neeko.
"""

from __future__ import annotations

# ---------------------------------------------------------------- palette ---

BACKGROUND = "#0B111C"        # window ground, deep navy
SURFACE = "#111A29"           # elevated panel
SURFACE_HOVER = "#172336"
SURFACE_ACTIVE = "#1E2D45"
SURFACE_SUNKEN = "#080D16"    # inputs, wells

BORDER = "#1E2A3D"
BORDER_STRONG = "#2C3D55"

TEXT_PRIMARY = "#F4F7FC"
TEXT_SECONDARY = "#A6B4CA"
TEXT_MUTED = "#6B7B93"

ACCENT = "#FF8A3D"            # orange, the signature
ACCENT_HOVER = "#FFA260"
ACCENT_PRESSED = "#E8701F"
ACCENT_INK = "#241206"        # text that sits on orange

BLUE = "#5CC8F5"              # light blue, the state colour
BLUE_HOVER = "#82D8F8"
BLUE_DEEP = "#2A94C8"

SUCCESS = "#4ADE9B"
WARNING = "#F5C451"
ERROR = "#F87171"
NEEKO = "#C86BD8"             # a restrained nod to her palette

# ---------------------------------------------------------------- spacing ---

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32

RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_XL = 20

# Control geometry, so nothing is sized by eye.
CONTROL_HEIGHT = 34
BUTTON_HEIGHT = 32
TOGGLE_WIDTH = 40
TOGGLE_HEIGHT = 22
ICON_SM = 28
ICON_MD = 40
ICON_LG = 56

WINDOW_WIDTH = 452
WINDOW_MIN_HEIGHT = 560
WINDOW_MAX_HEIGHT = 860
SHADOW_MARGIN = 16

# --------------------------------------------------------------- movement ---

DURATION_FAST = 120
DURATION_NORMAL = 180
DURATION_SLOW = 260

# ------------------------------------------------------------- typography ---

FONT = "Segoe UI"
MONO = "Consolas"

TYPE = {
    "display": (20, 600),
    "title": (15, 600),
    "metric": (23, 700),
    "body": (13, 400),
    "body-strong": (13, 600),
    "secondary": (12, 400),
    "small": (11, 400),
    "caption": (10, 700),
}


def font_css(role: str, colour: str) -> str:
    size, weight = TYPE[role]
    spacing = "letter-spacing: 1.3px;" if role == "caption" else ""
    return f"font-size: {size}px; font-weight: {weight}; color: {colour}; {spacing}"


def rgba(hex_colour: str, alpha: float) -> str:
    value = hex_colour.lstrip("#")
    red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {alpha:.3f})"


# ------------------------------------------------------------- stylesheet ---


def stylesheet() -> str:
    """Only the stock Qt controls; everything with real shape is painted."""
    return f"""
    QWidget {{
        color: {TEXT_PRIMARY};
        font-family: "{FONT}";
        font-size: 13px;
    }}

    QLabel#display      {{ {font_css("display", TEXT_PRIMARY)} }}
    QLabel#title        {{ {font_css("title", TEXT_PRIMARY)} }}
    QLabel#metric       {{ {font_css("metric", TEXT_PRIMARY)} }}
    QLabel#body         {{ {font_css("body", TEXT_PRIMARY)} }}
    QLabel#body-strong  {{ {font_css("body-strong", TEXT_PRIMARY)} }}
    QLabel#secondary    {{ {font_css("secondary", TEXT_SECONDARY)} }}
    QLabel#small        {{ {font_css("small", TEXT_MUTED)} }}
    QLabel#caption      {{ {font_css("caption", TEXT_MUTED)} }}
    QLabel#accent       {{ {font_css("body-strong", ACCENT)} }}
    QLabel#blue         {{ {font_css("secondary", BLUE)} }}
    QLabel#success      {{ {font_css("small", SUCCESS)} }}
    QLabel#warning      {{ {font_css("small", WARNING)} }}
    QLabel#error        {{ {font_css("small", ERROR)} }}

    QLineEdit {{
        background: {SURFACE_SUNKEN};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM}px;
        padding: 0px 12px;
        min-height: {CONTROL_HEIGHT}px;
        max-height: {CONTROL_HEIGHT}px;
        color: {TEXT_PRIMARY};
        selection-background-color: {ACCENT_PRESSED};
        selection-color: {TEXT_PRIMARY};
    }}
    QLineEdit:hover {{ border: 1px solid {BORDER_STRONG}; }}
    QLineEdit:focus {{ border: 1px solid {BLUE}; background: {SURFACE}; }}

    QPushButton {{
        background: {SURFACE_HOVER};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM}px;
        padding: 0px 16px;
        min-height: {BUTTON_HEIGHT}px;
        color: {TEXT_PRIMARY};
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover   {{ background: {SURFACE_ACTIVE}; border: 1px solid {BORDER_STRONG}; }}
    QPushButton:pressed {{ background: {SURFACE}; }}
    QPushButton:focus   {{ border: 1px solid {BLUE}; }}
    QPushButton:disabled {{ color: {TEXT_MUTED}; background: {SURFACE}; }}

    QPushButton#primary {{
        background: {ACCENT};
        border: 1px solid {ACCENT};
        color: {ACCENT_INK};
    }}
    QPushButton#primary:hover   {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
    QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}

    QPushButton#link {{
        background: transparent;
        border: none;
        color: {BLUE};
        padding: 0px 4px;
        min-height: 20px;
        font-size: 12px;
    }}
    QPushButton#link:hover  {{ color: {BLUE_HOVER}; }}
    QPushButton#link:focus  {{ border: none; text-decoration: underline; }}

    QListWidget {{
        background: transparent;
        border: none;
        outline: none;
    }}
    QListWidget::item {{
        border-radius: {RADIUS_SM}px;
        padding: 0px;
        margin: 1px 0px;
        color: {TEXT_PRIMARY};
    }}
    QListWidget::item:hover    {{ background: {SURFACE_HOVER}; }}
    QListWidget::item:selected {{ background: {rgba(ACCENT, 0.16)}; color: {TEXT_PRIMARY}; }}

    QTextEdit {{
        background: {SURFACE_SUNKEN};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM}px;
        font-family: "{MONO}", monospace;
        font-size: 11px;
        color: {TEXT_SECONDARY};
        padding: 6px;
    }}

    QComboBox {{
        background: {SURFACE_SUNKEN};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM}px;
        padding: 0px 10px;
        min-height: {CONTROL_HEIGHT}px;
        color: {TEXT_PRIMARY};
    }}
    QComboBox:hover {{ border: 1px solid {BORDER_STRONG}; }}
    QComboBox:focus {{ border: 1px solid {BLUE}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background: {SURFACE};
        border: 1px solid {BORDER_STRONG};
        border-radius: {RADIUS_SM}px;
        selection-background-color: {rgba(ACCENT, 0.18)};
        color: {TEXT_PRIMARY};
        padding: 4px;
        outline: none;
    }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
    QScrollBar::handle:vertical {{
        background: {BORDER_STRONG};
        border-radius: 4px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {BLUE_DEEP}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

    QToolTip {{
        background: {SURFACE};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STRONG};
        border-radius: {RADIUS_SM}px;
        padding: 6px 9px;
    }}

    QDialog {{ background: {BACKGROUND}; }}
    """
