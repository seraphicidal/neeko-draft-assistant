"""The main window: one champion card, everything else quiet around it."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.settings import MAX_DELAY
from core.version import __version__
from league import champion_art
from ui import assets, neeko, theme
from ui.widgets import (
    Avatar,
    ChampionSearch,
    ChampionShowcase,
    Hairline,
    MiniChampion,
    Slider,
    SpeechLine,
    StatePill,
    Switch,
    SwitchRow,
    TimerBar,
    WindowButton,
    caption,
    colour,
    label,
    row,
)

WINDOW_WIDTH = 436
SHADOW = 18
HEADER_HEIGHT = 96
DRAFT_PHASE_SECONDS = 30.0


class HeaderBar(QWidget):
    """Neeko, the app's name, and the window controls, on the painted banner."""

    minimise = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(HEADER_HEIGHT)
        self._banner = self._load(assets.HERO_BG)
        self._art = self._load(assets.full_art())
        self._drag_from: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 10, 12)
        layout.setSpacing(13)

        self.avatar = Avatar(assets.avatar(), size=62)
        layout.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignVCenter)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addStretch(1)
        titles.addWidget(label("NEEKO'S LITTLE", "caption"))
        titles.addWidget(label("Draft Assistant", "display"))
        self.version_label = label(f"v{__version__}", "small")
        titles.addWidget(self.version_label)
        titles.addStretch(1)
        layout.addLayout(titles, 1)

        controls = QVBoxLayout()
        controls.setSpacing(0)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for kind, signal in (
            (WindowButton.MINIMISE, self.minimise),
            (WindowButton.CLOSE, self.close_requested),
        ):
            button = WindowButton(kind)
            button.clicked.connect(signal.emit)
            buttons.addWidget(button)
        controls.addLayout(buttons)
        controls.addStretch(1)
        layout.addLayout(controls)

    @staticmethod
    def _load(path) -> QPixmap | None:
        if path is None or not path.exists():
            return None
        pixmap = QPixmap(str(path))
        return None if pixmap.isNull() else pixmap

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        clip = QPainterPath()
        clip.addRoundedRect(
            0, 0, self.width(), self.height() + theme.RADIUS, theme.RADIUS, theme.RADIUS
        )
        painter.setClipPath(clip)

        if self._banner is not None:
            painter.drawPixmap(
                self.rect(),
                self._banner.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )
        else:
            painter.fillRect(self.rect(), QColor(theme.NAVY_850))

        if self._art is not None:
            scaled = self._art.scaledToHeight(
                int(self.height() * 1.7), Qt.TransformationMode.SmoothTransformation
            )
            painter.setOpacity(0.26)
            painter.drawPixmap(self.width() - scaled.width() + 24, -34, scaled)
            painter.setOpacity(1.0)

        # Settle the banner into the window so the seam does not show.
        fade = QLinearGradient(0, self.height() - 26, 0, self.height())
        fade.setColorAt(0.0, colour(theme.NAVY_900, 0.0))
        fade.setColorAt(1.0, colour(theme.NAVY_900, 1.0))
        painter.fillRect(0, self.height() - 26, self.width(), 26, fade)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._drag_from is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        self._drag_from = None


class UpdateBanner(QWidget):
    """A slim strip that only appears when there is genuinely something new."""

    update_now = Signal()
    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(46)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 12, 6)
        layout.setSpacing(10)

        self.message = label("", "body")
        layout.addWidget(self.message, 1)

        self.update_button = QPushButton("Update now")
        self.update_button.setObjectName("primary")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(self.update_now.emit)
        layout.addWidget(self.update_button)

        later = QPushButton("Later")
        later.setObjectName("link")
        later.setCursor(Qt.CursorShape.PointingHandCursor)
        later.clicked.connect(self.dismissed.emit)
        layout.addWidget(later)
        self.hide()

    def offer(self, version: str) -> None:
        self.message.setText(f"Neeko found something new!  Version {version} is available.")
        self.update_button.setEnabled(True)
        self.update_button.setText("Update now")
        self.show()

    def working(self, text: str) -> None:
        self.message.setText(text)
        self.update_button.setEnabled(False)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour(theme.ORANGE, 0.13))
        painter.drawRect(self.rect())
        painter.setBrush(colour(theme.ORANGE))
        painter.drawRect(0, 0, 3, self.height())


class MainWindow(QWidget):
    quit_requested = Signal()
    settings_requested = Signal()
    pause_toggled = Signal(bool)
    art_wanted = Signal(str, int)
    update_requested = Signal()

    def __init__(self, settings, catalog) -> None:
        super().__init__()
        self.settings = settings
        self.catalog = catalog
        self._icons: dict[int, QPixmap] = {}
        self._splashes: dict[int, QPixmap] = {}
        self._state = ""
        self._reaction_until = 0.0

        self.setWindowTitle("Neeko's Draft Assistant")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SHADOW, SHADOW, SHADOW, SHADOW)

        self.root = QFrame()
        self.root.setObjectName("root")
        shadow = QGraphicsDropShadowEffect(self.root)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 200))
        self.root.setGraphicsEffect(shadow)
        outer.addWidget(self.root)

        body = QVBoxLayout(self.root)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.header = HeaderBar()
        self.header.minimise.connect(self.showMinimized)
        self.header.close_requested.connect(self.close)
        self.header.avatar.clicked.connect(self.settings_requested.emit)
        body.addWidget(self.header)

        self.update_banner = UpdateBanner()
        self.update_banner.update_now.connect(self.update_requested.emit)
        self.update_banner.dismissed.connect(self.update_banner.hide)
        body.addWidget(self.update_banner)

        content = QVBoxLayout()
        content.setContentsMargins(16, 4, 16, 0)
        content.setSpacing(0)
        self._build_status(content)
        self._build_champion(content)
        self._build_chat(content)
        self._build_queue(content)
        body.addLayout(content)
        body.addLayout(self._build_footer())

        self._reaction_timer = QTimer(self)
        self._reaction_timer.setSingleShot(True)
        self._reaction_timer.timeout.connect(self._settle_mood)

        self._load_from_settings()
        self.setFixedWidth(WINDOW_WIDTH + 2 * SHADOW)
        self.resize(WINDOW_WIDTH + 2 * SHADOW, self._preferred_height())

    def _preferred_height(self) -> int:
        """Exactly as tall as the content, unless the screen is smaller."""
        self.root.adjustSize()
        wanted = self.root.sizeHint().height() + 2 * SHADOW
        screen = self.screen()
        available = screen.availableGeometry().height() if screen else 900
        return max(560, min(wanted, available - 50))

    # -- sections ---------------------------------------------------------

    def _build_status(self, parent: QVBoxLayout) -> None:
        top = QHBoxLayout()
        top.setContentsMargins(0, 6, 0, 0)
        self.pill = StatePill()
        top.addWidget(self.pill)
        top.addStretch(1)
        self.turn_label = label("", "accent")
        top.addWidget(self.turn_label)
        parent.addLayout(top)

        self.speech = SpeechLine()
        parent.addWidget(self.speech)

        timer_row = QHBoxLayout()
        timer_row.setContentsMargins(0, 6, 0, 0)
        timer_row.setSpacing(9)
        self.timer_bar = TimerBar()
        self.timer_text = label("", "small")
        self.timer_text.setMinimumWidth(30)
        timer_row.addWidget(self.timer_bar, 1)
        timer_row.addWidget(self.timer_text)
        self.timer_row = timer_row
        parent.addLayout(timer_row)

        self.problem = label("", "warning")
        self.problem.setWordWrap(True)
        self.problem.hide()
        parent.addWidget(self.problem)

        self._show_timer(False)
        parent.addSpacing(12)

    def _build_champion(self, parent: QVBoxLayout) -> None:
        self.showcase = ChampionShowcase()
        self.showcase.declare_toggled.connect(self._on_declare)
        self.showcase.lock_toggled.connect(self._on_lock)
        parent.addWidget(self.showcase)
        parent.addSpacing(9)

        self.search = ChampionSearch(self.catalog, "Search champion...")
        self.search.chosen.connect(self._on_champion_chosen)
        parent.addWidget(self.search)
        parent.addSpacing(9)

        backup = QHBoxLayout()
        backup.setSpacing(10)
        backup.addWidget(caption("Backup"))
        self.backup_chip = MiniChampion()
        backup.addWidget(self.backup_chip)
        self.backup_name = label("none", "muted")
        backup.addWidget(self.backup_name, 1)

        self.backup_button = QPushButton("choose")
        self.backup_button.setObjectName("link")
        self.backup_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.backup_button.clicked.connect(self._toggle_backup_search)
        backup.addWidget(self.backup_button)
        parent.addLayout(backup)

        self.backup_search = ChampionSearch(self.catalog, "Search backup champion...")
        self.backup_search.chosen.connect(self._on_backup_chosen)
        self.backup_search.hide()
        parent.addWidget(self.backup_search)
        parent.addSpacing(12)

        parent.addWidget(Hairline())
        parent.addSpacing(12)

    def _build_chat(self, parent: QVBoxLayout) -> None:
        head = QHBoxLayout()
        head.addWidget(caption("Draft chat"))
        head.addStretch(1)
        self.chat_switch = Switch()
        self.chat_switch.toggled.connect(self._on_chat_toggled)
        head.addWidget(self.chat_switch)
        parent.addLayout(head)
        parent.addSpacing(7)

        self.message_edit = QLineEdit()
        self.message_edit.setPlaceholderText("say something in champion select")
        self.message_edit.setMaxLength(200)
        self.message_edit.textChanged.connect(self._on_message_changed)
        parent.addWidget(self.message_edit)

        self.chat_status = label("", "small")
        parent.addWidget(self.chat_status)
        parent.addSpacing(12)
        parent.addWidget(Hairline())
        parent.addSpacing(12)

    def _build_queue(self, parent: QVBoxLayout) -> None:
        head = QHBoxLayout()
        head.addWidget(caption("Queue"))
        head.addStretch(1)
        self.accept_state = label("ON", "small")
        head.addWidget(self.accept_state)
        self.accept_switch = Switch()
        self.accept_switch.toggled.connect(self._on_accept_toggled)
        head.addWidget(self.accept_switch)
        parent.addLayout(head)
        parent.addSpacing(4)

        delay = QHBoxLayout()
        delay.setSpacing(10)
        delay.addWidget(label("Accept delay", "muted"))
        delay.addStretch(1)
        self.delay_value = label("", "accent")
        delay.addWidget(self.delay_value)
        parent.addLayout(delay)

        self.delay_slider = Slider(maximum=MAX_DELAY, step=0.5)
        self.delay_slider.valueChanged.connect(self._on_delay_changed)
        parent.addWidget(self.delay_slider)

        self.queue_stats = label("", "small")
        parent.addWidget(self.queue_stats)

    def _build_footer(self) -> QHBoxLayout:
        strip = QHBoxLayout()
        strip.setContentsMargins(16, 10, 16, 14)
        strip.setSpacing(8)

        self.action_label = label("", "small")
        strip.addWidget(self.action_label, 1)

        settings_button = QPushButton("Settings")
        settings_button.setObjectName("quiet")
        settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_button.clicked.connect(self.settings_requested.emit)
        strip.addWidget(settings_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setObjectName("quiet")
        self.pause_button.setCheckable(True)
        self.pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_button.toggled.connect(self._on_pause)
        strip.addWidget(self.pause_button)
        return strip

    # -- settings <-> widgets ---------------------------------------------

    def _load_from_settings(self) -> None:
        settings = self.settings
        self._apply_champion(settings.preferred_champion_id, settings.preferred_champion_name)
        self._apply_backup(settings.backup_champion_id, settings.backup_champion_name)
        self.showcase.set_states(settings.auto_declare, settings.auto_pick)

        self.message_edit.blockSignals(True)
        self.message_edit.setText(settings.chat_message)
        self.message_edit.blockSignals(False)
        self.chat_switch.setChecked(settings.chat_enabled)

        self.accept_switch.setChecked(settings.auto_accept)
        self._render_accept_state(settings.auto_accept)
        self.delay_slider.setValue(settings.accept_delay)
        self._render_delay(settings.accept_delay)
        self._render_stats()

    def _apply_champion(self, champion_id: int, name: str) -> None:
        title = self.catalog.title_of(champion_id)
        self.showcase.set_champion(name, title)
        if champion_id:
            icon = self._icons.get(champion_id)
            splash = self._splashes.get(champion_id)
            self.showcase.set_icon(icon)
            self.showcase.set_splash(splash)
            if icon is None:
                self.art_wanted.emit(champion_art.ICON, champion_id)
            if splash is None:
                self.art_wanted.emit(champion_art.SPLASH, champion_id)
        else:
            self.showcase.set_icon(None)
            self.showcase.set_splash(None)

    def _apply_backup(self, champion_id: int, name: str) -> None:
        self.backup_chip.set_champion(name)
        self.backup_chip.setVisible(bool(champion_id))
        self.backup_name.setText(name or "none")
        self.backup_name.setStyleSheet(
            f"color: {theme.SKY if champion_id else theme.DIM}; font-size: 12px;"
        )
        self.backup_button.setText("change" if champion_id else "choose")
        if champion_id:
            icon = self._icons.get(champion_id)
            if icon is not None:
                self.backup_chip.set_icon(icon)
            else:
                self.art_wanted.emit(champion_art.ICON, champion_id)

    def refresh_names_from_catalog(self) -> None:
        for id_attr, name_attr in (
            ("preferred_champion_id", "preferred_champion_name"),
            ("backup_champion_id", "backup_champion_name"),
        ):
            champion_id = getattr(self.settings, id_attr)
            if champion_id:
                name = self.catalog.name_of(champion_id) or getattr(self.settings, name_attr)
                setattr(self.settings, name_attr, name)
        self._apply_champion(
            self.settings.preferred_champion_id, self.settings.preferred_champion_name
        )
        self._apply_backup(
            self.settings.backup_champion_id, self.settings.backup_champion_name
        )

    def set_art(self, kind: str, champion_id: int, data: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        store = self._icons if kind == champion_art.ICON else self._splashes
        store[champion_id] = pixmap

        if champion_id == self.settings.preferred_champion_id:
            if kind == champion_art.ICON:
                self.showcase.set_icon(pixmap)
            else:
                self.showcase.set_splash(pixmap)
        if champion_id == self.settings.backup_champion_id and kind == champion_art.ICON:
            self.backup_chip.set_icon(pixmap)

    # -- handlers ----------------------------------------------------------

    def _save(self) -> None:
        self.settings.save()

    def _save_soon(self) -> None:
        if not hasattr(self, "_save_timer"):
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._save)
        self._save_timer.start(600)

    def _on_champion_chosen(self, champion_id: int, name: str) -> None:
        self.settings.preferred_champion_id = champion_id
        self.settings.preferred_champion_name = name
        self._apply_champion(champion_id, name)
        self._save()
        self.speech.say(f"Neeko will play {name}!", theme.ORANGE)

    def _toggle_backup_search(self) -> None:
        showing = not self.backup_search.isVisible()
        self.backup_search.setVisible(showing)
        if showing:
            self.backup_search.field.setFocus()
        else:
            self.backup_search.clear()

    def _on_backup_chosen(self, champion_id: int, name: str) -> None:
        self.settings.backup_champion_id = champion_id
        self.settings.backup_champion_name = name
        self._apply_backup(champion_id, name)
        self.backup_search.hide()
        self.backup_search.clear()
        self._save()

    def _on_declare(self, value: bool) -> None:
        self.settings.auto_declare = value
        self._save()

    def _on_lock(self, value: bool) -> None:
        self.settings.auto_pick = value
        self._save()

    def _on_chat_toggled(self, value: bool) -> None:
        self.settings.chat_enabled = value
        self._save()

    def _on_message_changed(self, text: str) -> None:
        self.settings.chat_message = text
        self._save_soon()

    def _on_accept_toggled(self, value: bool) -> None:
        self.settings.auto_accept = value
        self._render_accept_state(value)
        self._save()

    def _render_accept_state(self, value: bool) -> None:
        self.accept_state.setText("ON" if value else "OFF")
        self.accept_state.setStyleSheet(
            f"color: {theme.ORANGE if value else theme.DIM}; font-size: 11px; font-weight: 700;"
        )

    def _on_delay_changed(self, value: float) -> None:
        self.settings.accept_delay = value
        self._render_delay(value)
        self._save_soon()

    def _render_delay(self, value: float) -> None:
        self.delay_value.setText("instantly" if value == 0 else f"{value:.1f}s")

    def _on_pause(self, paused: bool) -> None:
        self.pause_button.setText("Paused" if paused else "Pause")
        self.pause_button.setStyleSheet(
            f"color: {theme.ORANGE};" if paused else ""
        )
        self.pause_toggled.emit(paused)

    def _render_stats(self) -> None:
        self.queue_stats.setText(
            f"{self.settings.accepted_total} queues accepted   ·   "
            f"{self.settings.picks_total} champions locked in"
        )

    def refresh_counters(self) -> None:
        self._render_stats()
        self._save()

    # -- live state ---------------------------------------------------------

    def _show_timer(self, visible: bool) -> None:
        self.timer_bar.setVisible(visible)
        self.timer_text.setVisible(visible)

    def apply_status(self, status) -> None:
        tint = theme.STATE_COLOURS.get(status.state, theme.MUTED)
        headline = status.phase_label if status.connected else "Waiting for League"
        self.pill.set_state(headline.upper(), tint)

        self.turn_label.setText(f"Your turn: {status.turn}" if status.turn else "")
        self._show_timer(status.in_draft)
        if status.in_draft:
            self.timer_bar.set_fraction(min(1.0, status.time_left / DRAFT_PHASE_SECONDS))
            self.timer_text.setText(f"{status.time_left:.0f}s")

        self.problem.setText(status.problem)
        self.problem.setVisible(bool(status.problem))

        self.showcase.set_highlight(status.state in ("MY_TURN", "READY_CHECK"))

        if self.settings.chat_enabled:
            if status.chat_failed:
                self.chat_status.setText("could not send the message")
                self.chat_status.setStyleSheet(f"color: {theme.DANGER}; font-size: 11px;")
            elif status.chat_sent:
                self.chat_status.setText("message sent this draft")
                self.chat_status.setStyleSheet(f"color: {theme.SUCCESS}; font-size: 11px;")
            else:
                self.chat_status.setText("waiting for champion select")
                self.chat_status.setStyleSheet(f"color: {theme.DIM}; font-size: 11px;")
        else:
            self.chat_status.setText("")

        if status.state != self._state:
            self._state = status.state
            self._settle_mood()
        elif status.problem and not self._reaction_timer.isActive():
            self.speech.say(neeko.WORRIED.line, neeko.WORRIED.colour)
            self.header.avatar.set_mood(neeko.WORRIED.colour, neeko.WORRIED.energy)

    def _settle_mood(self) -> None:
        mood = neeko.for_state(self._state)
        self.speech.say(mood.line, mood.colour)
        self.header.avatar.set_mood(mood.colour, mood.energy)

    def show_action(self, text: str, level: str) -> None:
        self.action_label.setText(text)
        self.action_label.setStyleSheet(
            f"color: {theme.LEVEL_COLOURS.get(level, theme.MUTED)}; font-size: 11px;"
        )
        reaction = neeko.for_action(text)
        if reaction is not None:
            self.speech.say(reaction.line, reaction.colour)
            self.header.avatar.set_mood(reaction.colour, reaction.energy)
            self._reaction_timer.start(int(neeko.REACTION_SECONDS * 1000))

    # -- updates -------------------------------------------------------------

    def offer_update(self, release) -> None:
        self.update_banner.offer(release.version)

    def update_progress(self, text: str) -> None:
        self.update_banner.working(text)

    # -- window --------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self.settings.minimize_to_tray:
            event.ignore()
            self.hide()
            self.header.avatar.set_animated(False)
        else:
            event.accept()
            self.quit_requested.emit()

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.header.avatar.set_animated(True)
