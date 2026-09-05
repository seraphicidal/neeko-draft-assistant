"""The stage: the part of the dashboard that changes with the situation.

One scene per situation rather than one per state, so the window always answers
"what is happening right now" without the user reading a single control.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from ui import assets, status as status_module, theme
from ui.widgets import (
    ChampionHero,
    Chip,
    NeekoArt,
    ProgressBar,
    load_pixmap,
    text,
)

STAGE_HEIGHT = 226   # tall enough for the draft scene, the busiest one


class Scene(QWidget):
    """Illustration, headline, one supporting line. Subclasses add the rest."""

    ART_HEIGHT = 118

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.layout_column = QVBoxLayout(self)
        self.layout_column.setContentsMargins(0, 0, 0, 0)
        self.layout_column.setSpacing(theme.SPACE_1)
        # Leading and trailing stretch, so a short scene sits in the middle of
        # the stage rather than leaving a band of nothing underneath it.
        self.layout_column.addStretch(1)

        self.art = NeekoArt(self.ART_HEIGHT)
        self.layout_column.addWidget(self.art)

        self.headline = text("", "display")
        self.headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_column.addWidget(self.headline)

        self.detail = text("", "secondary")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        self.layout_column.addWidget(self.detail)
        self.layout_column.addStretch(1)

    def apply(self, status, view, context) -> None:
        self.headline.setText(status.headline)
        self.detail.setText(status.detail)
        self.art.set_art(status.art, context.art_for(status.art))


class OfflineScene(Scene):
    ART_HEIGHT = 124


class IdleScene(Scene):
    ART_HEIGHT = 118


class QueueScene(Scene):
    ART_HEIGHT = 110

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.progress = ProgressBar()
        self.layout_column.insertWidget(self.layout_column.count() - 1, self.progress)
        self.progress.set_progress(1.0, theme.BLUE)


class ReadyScene(Scene):
    """The queue pop. The one moment the app should be impossible to miss."""

    ART_HEIGHT = 96

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.countdown = text("", "metric")
        self.countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = ProgressBar()

        index = self.layout_column.count() - 1
        self.layout_column.insertWidget(index, self.countdown)
        self.layout_column.insertSpacing(index + 1, theme.SPACE_2)
        self.layout_column.insertWidget(index + 2, self.progress)

    def apply(self, status, view, context) -> None:
        super().apply(status, view, context)
        remaining = context.accept_countdown
        if remaining is None:
            self.countdown.setText("")
            self.progress.set_progress(1.0, theme.SUCCESS)
            return
        self.countdown.setText(f"{remaining:.1f}s")
        self.countdown.setStyleSheet(theme.font_css("metric", theme.ACCENT))
        delay = max(0.1, context.accept_delay)
        self.progress.set_progress(1.0 - remaining / delay, theme.ACCENT)


class DraftScene(QWidget):
    """Champion select: the champion, the turn, the clock, and what is armed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(theme.SPACE_2)

        self.hero = ChampionHero(124)
        column.addWidget(self.hero)

        turn_row = QHBoxLayout()
        turn_row.setSpacing(theme.SPACE_2)
        self.turn = text("", "title")
        self.clock = text("", "body-strong")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        turn_row.addWidget(self.turn, 1)
        turn_row.addWidget(self.clock)
        column.addLayout(turn_row)

        self.timer = ProgressBar()
        column.addWidget(self.timer)

        chips = QHBoxLayout()
        chips.setSpacing(theme.SPACE_2)
        self.declare_chip = Chip("Declare")
        self.lock_chip = Chip("Lock in")
        self.chat_chip = Chip("Chat")
        for chip in (self.declare_chip, self.lock_chip, self.chat_chip):
            chips.addWidget(chip)
        chips.addStretch(1)
        column.addLayout(chips)
        column.addStretch(1)

    def apply(self, status, view, context) -> None:
        self.turn.setText(status.headline)
        self.turn.setStyleSheet(theme.font_css("title", status.tone))

        champion_id = view.declared_champion or context.preferred_id
        self.hero.set_champion(context.name_of(champion_id), status.tone)
        self.hero.set_icon(context.champion_icon(champion_id))
        self.hero.set_splash(context.champion_splash(champion_id))

        seconds = view.time_left
        self.clock.setText(f"{seconds:.0f}s" if view.in_draft else "")
        fraction = min(1.0, seconds / context.draft_phase_seconds) if view.in_draft else 0.0
        self.timer.set_progress(
            fraction, theme.BLUE if fraction > 0.35 else theme.ACCENT
        )

        self.declare_chip.set_state(
            "armed" if context.auto_declare else "off",
            done=bool(view.declared_champion),
        )
        self.lock_chip.set_state("armed" if context.auto_pick else "off",
                                done=view.state == "LOCKED")
        if not context.chat_enabled:
            self.chat_chip.set_state("off")
        elif view.chat_failed:
            self.chat_chip.set_state("failed")
        else:
            self.chat_chip.set_state("armed", done=view.chat_sent)


class GameScene(Scene):
    ART_HEIGHT = 126


class Stage(QStackedWidget):
    """Swaps between scenes as the situation changes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(STAGE_HEIGHT)
        self._scenes = {
            status_module.OFFLINE: OfflineScene(),
            status_module.IDLE: IdleScene(),
            status_module.QUEUE: QueueScene(),
            status_module.READY: ReadyScene(),
            status_module.DRAFT: DraftScene(),
            status_module.GAME: GameScene(),
        }
        for scene in self._scenes.values():
            self.addWidget(scene)

    def apply(self, status, view, context) -> None:
        scene = self._scenes[status.scene]
        scene.apply(status, view, context)
        if self.currentWidget() is not scene:
            self.setCurrentWidget(scene)

    def draft_scene(self) -> DraftScene:
        return self._scenes[status_module.DRAFT]


class ArtCache:
    """Loads and keeps the Neeko illustrations, so no file is read twice."""

    def __init__(self) -> None:
        self._art: dict[str, QPixmap | None] = {}

    def get(self, role: str) -> QPixmap | None:
        if role not in self._art:
            self._art[role] = load_pixmap(assets.art(role))
        return self._art[role]
