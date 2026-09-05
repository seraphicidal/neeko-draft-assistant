"""The dashboard.

Header, live status, a stage that changes with the situation, the controls that
matter, and a footer. The window observes state and renders it -- every decision
about the draft is made in `core/state_machine.py`, never here.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.settings import MAX_DELAY
from core.version import APP_NAME, __version__
from league import champion_art
from ui import assets, status as status_module, theme
from ui.stage import ArtCache, Stage
from ui.widgets import (
    Avatar,
    ChampionTile,
    Chip,
    Divider,
    SearchOverlay,
    SettingRow,
    Slider,
    StatusPill,
    Toast,
    Toggle,
    WindowButton,
    caption,
    colour,
    paint_shadow,
    text,
)

DRAFT_PHASE_SECONDS = 30.0
PRIMARY = "primary"
BACKUP = "backup"


class HeaderBar(QWidget):
    """Name, version, Neeko, and the window controls. Also the drag handle."""

    minimise = Signal()
    close_requested = Signal()
    avatar_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(60)
        self._drag_from: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_4, theme.SPACE_2, theme.SPACE_2, theme.SPACE_2)
        layout.setSpacing(theme.SPACE_3)

        self.avatar = Avatar(assets.avatar(), size=38)
        self.avatar.clicked.connect(self.avatar_clicked.emit)
        layout.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignVCenter)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addStretch(1)
        titles.addWidget(text(APP_NAME, "title"))
        titles.addWidget(text(f"Version {__version__}", "small"))
        titles.addStretch(1)
        layout.addLayout(titles, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for kind, signal in (
            (WindowButton.MINIMISE, self.minimise),
            (WindowButton.CLOSE, self.close_requested),
        ):
            button = WindowButton(kind)
            button.clicked.connect(signal.emit)
            buttons.addWidget(button)
        controls = QVBoxLayout()
        controls.setSpacing(0)
        controls.addLayout(buttons)
        controls.addStretch(1)
        layout.addLayout(controls)

    # The whole strip drags the window, except where a control sits.
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
    """Appears only when there is genuinely a newer version."""

    update_now = Signal()
    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_4, theme.SPACE_2, theme.SPACE_3, theme.SPACE_2)
        layout.setSpacing(theme.SPACE_2)

        self.message = text("", "body")
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
        self.message.setText(f"Version {version} is ready to install.")
        self.update_button.setEnabled(True)
        self.show()

    def working(self, message: str) -> None:
        self.message.setText(message)
        self.update_button.setEnabled(False)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour(theme.ACCENT, 0.11))
        painter.drawRect(self.rect())
        painter.setBrush(colour(theme.ACCENT))
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
        self._neeko_art = ArtCache()
        self._state = ""
        self._picking = ""          # which slot the overlay is choosing for
        self._accept_countdown: float | None = None

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(theme.WINDOW_WIDTH + 2 * theme.SHADOW_MARGIN)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            theme.SHADOW_MARGIN, theme.SHADOW_MARGIN, theme.SHADOW_MARGIN, theme.SHADOW_MARGIN
        )

        self.root = QWidget()
        self.root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        outer.addWidget(self.root)

        body = QVBoxLayout(self.root)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.header = HeaderBar()
        self.header.minimise.connect(self.showMinimized)
        self.header.close_requested.connect(self.close)
        self.header.avatar_clicked.connect(self.settings_requested.emit)
        body.addWidget(self.header)

        self.update_banner = UpdateBanner()
        self.update_banner.update_now.connect(self.update_requested.emit)
        self.update_banner.dismissed.connect(self.update_banner.hide)
        body.addWidget(self.update_banner)

        body.addWidget(Divider(theme.SPACE_4))
        body.addLayout(self._build_status_strip())

        stage_wrap = QHBoxLayout()
        stage_wrap.setContentsMargins(theme.SPACE_4, 0, theme.SPACE_4, theme.SPACE_3)
        self.stage = Stage()
        stage_wrap.addWidget(self.stage)
        body.addLayout(stage_wrap)

        body.addWidget(Divider(theme.SPACE_4))
        body.addWidget(self._build_controls())
        body.addWidget(Divider(theme.SPACE_4))
        body.addLayout(self._build_footer())

        self.overlay = SearchOverlay(self.catalog, self.root)
        self.overlay.pixmap_for = self._icons.get
        self.overlay.chosen.connect(self._on_champion_chosen)
        self.overlay.dismissed.connect(self._close_overlay)
        self.overlay.art_wanted.connect(self.art_wanted.emit)

        self._reaction_timer = QTimer(self)
        self._reaction_timer.setSingleShot(True)
        self._reaction_timer.timeout.connect(self._settle_voice)

        self._load_from_settings()
        self.adjustSize()

    # ------------------------------------------------------------ layout ---

    def _build_status_strip(self) -> QHBoxLayout:
        strip = QHBoxLayout()
        strip.setContentsMargins(theme.SPACE_4, theme.SPACE_3, theme.SPACE_4, theme.SPACE_3)
        strip.setSpacing(theme.SPACE_3)

        self.pill = StatusPill()
        strip.addWidget(self.pill)
        strip.addStretch(1)
        self.summoner = text("", "small")
        strip.addWidget(self.summoner)
        return strip

    def _build_controls(self) -> QWidget:
        self.controls = QStackedWidget()
        self.controls.addWidget(self._build_draft_controls())
        self.controls.addWidget(self._build_playing_panel())
        return self.controls

    def _build_draft_controls(self) -> QWidget:
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(theme.SPACE_4, theme.SPACE_3, theme.SPACE_4, theme.SPACE_3)
        column.setSpacing(theme.SPACE_1)

        column.addWidget(caption("Your champions"))
        self.primary_tile = ChampionTile("Primary", primary=True)
        self.primary_tile.clicked.connect(lambda: self._open_overlay(PRIMARY))
        column.addWidget(self.primary_tile)

        self.backup_tile = ChampionTile("Backup", primary=False)
        self.backup_tile.clicked.connect(lambda: self._open_overlay(BACKUP))
        column.addWidget(self.backup_tile)

        self.declare_row = SettingRow(
            "Auto declare", "Hover your champion so the team can see it."
        )
        self.declare_row.toggled.connect(self._on_declare)
        column.addWidget(self.declare_row)

        self.lock_row = SettingRow(
            "Auto lock-in", "Lock the pick in as soon as it is yours. Cannot be undone."
        )
        self.lock_row.toggled.connect(self._on_lock)
        column.addWidget(self.lock_row)

        column.addSpacing(theme.SPACE_2)
        column.addWidget(Divider())
        column.addSpacing(theme.SPACE_2)

        chat_head = QHBoxLayout()
        chat_head.addWidget(caption("Draft chat"), 1)
        self.chat_toggle = Toggle()
        self.chat_toggle.setAccessibleName("Send the draft message automatically")
        self.chat_toggle.toggled.connect(self._on_chat)
        chat_head.addWidget(self.chat_toggle)
        column.addLayout(chat_head)
        column.addSpacing(theme.SPACE_1)

        self.message_edit = QLineEdit()
        self.message_edit.setPlaceholderText("Say something in champion select")
        self.message_edit.setMaxLength(200)
        self.message_edit.textChanged.connect(self._on_message)
        column.addWidget(self.message_edit)

        self.chat_status = text("", "small")
        column.addWidget(self.chat_status)

        column.addSpacing(theme.SPACE_2)
        column.addWidget(Divider())
        column.addSpacing(theme.SPACE_2)

        queue_head = QHBoxLayout()
        queue_head.addWidget(caption("Queue"), 1)
        self.accept_state = text("", "caption")
        queue_head.addWidget(self.accept_state)
        self.accept_toggle = Toggle()
        self.accept_toggle.setAccessibleName("Accept the queue automatically")
        self.accept_toggle.toggled.connect(self._on_accept)
        queue_head.addWidget(self.accept_toggle)
        column.addLayout(queue_head)

        delay_head = QHBoxLayout()
        delay_head.addWidget(text("Accept after", "small"), 1)
        self.delay_value = text("", "accent")
        delay_head.addWidget(self.delay_value)
        column.addLayout(delay_head)

        self.delay_slider = Slider(maximum=MAX_DELAY, step=0.5)
        self.delay_slider.setAccessibleName("Accept delay in seconds")
        self.delay_slider.valueChanged.connect(self._on_delay)
        column.addWidget(self.delay_slider)
        column.addStretch(1)
        return page

    def _build_playing_panel(self) -> QWidget:
        """Shown while a game is running.

        The draft controls are put away -- there is nothing to configure
        mid-game -- and the space is used to confirm what is armed for the
        next one instead of sitting empty.
        """
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(theme.SPACE_4, theme.SPACE_3, theme.SPACE_4, theme.SPACE_3)
        column.setSpacing(theme.SPACE_1)

        column.addWidget(caption("While you play"))
        note = text(
            "Neeko put the draft controls away. Everything is still armed for your next game.",
            "secondary",
        )
        note.setWordWrap(True)
        column.addWidget(note)
        column.addSpacing(theme.SPACE_3)

        column.addWidget(caption("Ready for the next game"))
        self._summary_values: dict[str, object] = {}
        for key, label in (
            ("primary", "Primary"),
            ("backup", "Backup"),
            ("declare", "Auto declare"),
            ("lock", "Auto lock-in"),
            ("chat", "Draft chat"),
            ("accept", "Auto accept"),
        ):
            line = QHBoxLayout()
            line.setContentsMargins(0, 3, 0, 3)
            line.addWidget(text(label, "body"), 1)
            value = text("", "body-strong")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            line.addWidget(value)
            self._summary_values[key] = value
            column.addLayout(line)

        column.addSpacing(theme.SPACE_3)
        column.addWidget(Divider())
        column.addSpacing(theme.SPACE_2)
        self.session_stats = text("", "small")
        column.addWidget(self.session_stats)
        column.addStretch(1)
        return page

    def _render_playing_summary(self) -> None:
        settings = self.settings
        pairs = {
            "primary": (settings.preferred_champion_name or "not chosen",
                        bool(settings.preferred_champion_id)),
            "backup": (settings.backup_champion_name or "none",
                       bool(settings.backup_champion_id)),
            "declare": ("ON" if settings.auto_declare else "OFF", settings.auto_declare),
            "lock": ("ON" if settings.auto_pick else "OFF", settings.auto_pick),
            "chat": ("ON" if settings.chat_enabled else "OFF", settings.chat_enabled),
            "accept": ("ON" if settings.auto_accept else "OFF", settings.auto_accept),
        }
        for key, (value, active) in pairs.items():
            widget = self._summary_values[key]
            widget.setText(value)
            widget.setStyleSheet(
                theme.font_css("body-strong", theme.ACCENT if active else theme.TEXT_MUTED)
            )

    def _build_footer(self) -> QHBoxLayout:
        strip = QHBoxLayout()
        strip.setContentsMargins(theme.SPACE_4, theme.SPACE_3, theme.SPACE_4, theme.SPACE_4)
        strip.setSpacing(theme.SPACE_2)

        self.toast = Toast()
        strip.addWidget(self.toast, 1)

        settings_button = QPushButton("Settings")
        settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_button.clicked.connect(self.settings_requested.emit)
        strip.addWidget(settings_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_button.toggled.connect(self._on_pause)
        strip.addWidget(self.pause_button)
        return strip

    # ------------------------------------------------------------ painting ---

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        body = QRectF(self.root.geometry())
        paint_shadow(painter, body, theme.RADIUS_XL)

        path = QPainterPath()
        path.addRoundedRect(body, theme.RADIUS_XL, theme.RADIUS_XL)
        painter.fillPath(path, colour(theme.BACKGROUND))
        painter.strokePath(path, colour(theme.BORDER))

    # ------------------------------------------------- settings <-> widgets ---

    def _load_from_settings(self) -> None:
        settings = self.settings
        self._apply_champion(PRIMARY, settings.preferred_champion_id, settings.preferred_champion_name)
        self._apply_champion(BACKUP, settings.backup_champion_id, settings.backup_champion_name)

        self.declare_row.setChecked(settings.auto_declare)
        self.lock_row.setChecked(settings.auto_pick)

        self.message_edit.blockSignals(True)
        self.message_edit.setText(settings.chat_message)
        self.message_edit.blockSignals(False)
        self.chat_toggle.setChecked(settings.chat_enabled)

        self.accept_toggle.setChecked(settings.auto_accept)
        self._render_accept(settings.auto_accept)
        self.delay_slider.setValue(settings.accept_delay)
        self._render_delay(settings.accept_delay)
        self._render_stats()

    def _apply_champion(self, slot: str, champion_id: int, name: str) -> None:
        tile = self.primary_tile if slot == PRIMARY else self.backup_tile
        tile.set_champion(champion_id, name)
        if champion_id:
            tile.set_pixmap(self._icons.get(champion_id))
            if champion_id not in self._icons:
                self.art_wanted.emit(champion_art.ICON, champion_id)
            if slot == PRIMARY and champion_id not in self._splashes:
                self.art_wanted.emit(champion_art.SPLASH, champion_id)

    def request_art(self) -> None:
        """Re-ask once the loader is connected; `__init__` runs before it is."""
        self._apply_champion(
            PRIMARY, self.settings.preferred_champion_id, self.settings.preferred_champion_name
        )
        self._apply_champion(
            BACKUP, self.settings.backup_champion_id, self.settings.backup_champion_name
        )

    def refresh_names_from_catalog(self) -> None:
        for slot, id_attr, name_attr in (
            (PRIMARY, "preferred_champion_id", "preferred_champion_name"),
            (BACKUP, "backup_champion_id", "backup_champion_name"),
        ):
            champion_id = getattr(self.settings, id_attr)
            if champion_id:
                name = self.catalog.name_of(champion_id) or getattr(self.settings, name_attr)
                setattr(self.settings, name_attr, name)
            self._apply_champion(slot, champion_id, getattr(self.settings, name_attr))

    def set_art(self, kind: str, champion_id: int, data: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        store = self._icons if kind == champion_art.ICON else self._splashes
        store[champion_id] = pixmap

        if kind == champion_art.ICON:
            self.overlay.set_pixmap(champion_id, pixmap)
            if champion_id == self.settings.preferred_champion_id:
                self.primary_tile.set_pixmap(pixmap)
            if champion_id == self.settings.backup_champion_id:
                self.backup_tile.set_pixmap(pixmap)
        if champion_id == self.settings.preferred_champion_id:
            draft = self.stage.draft_scene()
            if kind == champion_art.ICON:
                draft.hero.set_icon(pixmap)
            else:
                draft.hero.set_splash(pixmap)

    # ------------------------------------------------------------- overlay ---

    def _open_overlay(self, slot: str) -> None:
        self._picking = slot
        heading = "Choose your champion" if slot == PRIMARY else "Choose a backup champion"
        self.overlay.setFixedWidth(theme.WINDOW_WIDTH - 2 * theme.SPACE_5)
        self.overlay.adjustSize()
        self.overlay.move(
            theme.SPACE_5,
            self.header.height() + theme.SPACE_5,
        )
        self.overlay.open_for(heading)

    def _close_overlay(self) -> None:
        self._picking = ""
        self.overlay.hide()

    def _on_champion_chosen(self, champion_id: int, name: str) -> None:
        slot = self._picking or PRIMARY
        if slot == PRIMARY:
            self.settings.preferred_champion_id = champion_id
            self.settings.preferred_champion_name = name
        else:
            self.settings.backup_champion_id = champion_id
            self.settings.backup_champion_name = name
        self._apply_champion(slot, champion_id, name)
        self._close_overlay()
        self._save()
        self.toast.show_message(f"{name} set as your {slot} champion", theme.ACCENT)

    # ------------------------------------------------------------ handlers ---

    def _save(self) -> None:
        self.settings.save()

    def _save_soon(self) -> None:
        if not hasattr(self, "_save_timer"):
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._save)
        self._save_timer.start(600)

    def _on_declare(self, value: bool) -> None:
        self.settings.auto_declare = value
        self._save()

    def _on_lock(self, value: bool) -> None:
        self.settings.auto_pick = value
        self._save()

    def _on_chat(self, value: bool) -> None:
        self.settings.chat_enabled = value
        self._save()

    def _on_message(self, value: str) -> None:
        self.settings.chat_message = value
        self._save_soon()

    def _on_accept(self, value: bool) -> None:
        self.settings.auto_accept = value
        self._render_accept(value)
        self._save()

    def _render_accept(self, value: bool) -> None:
        self.accept_state.setText("ON" if value else "OFF")
        self.accept_state.setStyleSheet(
            theme.font_css("caption", theme.ACCENT if value else theme.TEXT_MUTED)
        )

    def _on_delay(self, value: float) -> None:
        self.settings.accept_delay = value
        self._render_delay(value)
        self._save_soon()

    def _render_delay(self, value: float) -> None:
        self.delay_value.setText(
            "instantly" if value == 0 else f"{value:.1f} seconds"
        )

    def _on_pause(self, paused: bool) -> None:
        self.pause_button.setText("Paused" if paused else "Pause")
        self.pause_toggled.emit(paused)

    def _render_stats(self) -> None:
        self.session_stats.setText(
            f"{self.settings.accepted_total} queues accepted   ·   "
            f"{self.settings.picks_total} champions locked in"
        )
        self._render_playing_summary()

    def refresh_counters(self) -> None:
        self._render_stats()
        self._save()

    # -------------------------------------------------------- live status ---

    def apply_status(self, view) -> None:
        status = status_module.for_state(view.state)
        self._accept_countdown = view.accept_in if view.accept_in > 0 else None

        self.pill.set_status(status.label, status.tone, status.live)
        self.header.avatar.set_tone(status.tone)
        self.summoner.setText(view.summoner)

        self.stage.apply(status, view, self)

        page = 1 if status.scene == status_module.GAME else 0
        if self.controls.currentIndex() != page:
            self.controls.setCurrentIndex(page)

        problem = status_module.humanise(view.problem)
        if problem:
            self.toast.show_message(problem, theme.WARNING)

        if self.settings.chat_enabled:
            if view.chat_failed:
                message, tone = "Couldn't send the message this draft.", theme.ERROR
            elif view.chat_sent:
                message, tone = "Message sent this draft.", theme.SUCCESS
            else:
                message, tone = "Sent once, when champion select opens.", theme.TEXT_MUTED
        else:
            message, tone = "Off. Neeko will stay quiet.", theme.TEXT_MUTED
        self.chat_status.setText(message)
        self.chat_status.setStyleSheet(theme.font_css("small", tone))

        if view.state != self._state:
            self._state = view.state
            if not self._reaction_timer.isActive():
                self._settle_voice()

    def _settle_voice(self) -> None:
        status = status_module.for_state(self._state)
        self.toast.show_message(status.voice, status.tone)

    def show_action(self, message: str, level: str) -> None:
        reaction = status_module.for_action(message)
        if reaction is not None:
            self.toast.show_message(reaction.voice, reaction.tone)
            self._reaction_timer.start(int(status_module.REACTION_SECONDS * 1000))
        else:
            self.toast.show_message(message, theme.TEXT_SECONDARY)

    # ------------------------------------------------- context for the stage ---
    # The scenes ask the window for what they need to draw; the window never
    # asks them anything back.

    def art_for(self, role: str) -> QPixmap | None:
        return self._neeko_art.get(role)

    def name_of(self, champion_id: int) -> str:
        return self.catalog.name_of(champion_id)

    def champion_icon(self, champion_id: int) -> QPixmap | None:
        return self._icons.get(champion_id)

    def champion_splash(self, champion_id: int) -> QPixmap | None:
        return self._splashes.get(champion_id)

    @property
    def preferred_id(self) -> int:
        return self.settings.preferred_champion_id

    @property
    def auto_declare(self) -> bool:
        return self.settings.auto_declare

    @property
    def auto_pick(self) -> bool:
        return self.settings.auto_pick

    @property
    def chat_enabled(self) -> bool:
        return self.settings.chat_enabled

    @property
    def accept_delay(self) -> float:
        return self.settings.accept_delay

    @property
    def accept_countdown(self) -> float | None:
        return self._accept_countdown

    @property
    def draft_phase_seconds(self) -> float:
        return DRAFT_PHASE_SECONDS

    # ------------------------------------------------------------- updates ---

    def offer_update(self, release) -> None:
        self.update_banner.offer(release.version)

    def update_progress(self, message: str) -> None:
        self.update_banner.working(message)

    # -------------------------------------------------------------- window ---

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.key() == Qt.Key.Key_Escape and self.overlay.isVisible():
            self._close_overlay()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self.settings.minimize_to_tray:
            event.ignore()
            self.hide()
            self._set_animations(False)
        else:
            event.accept()
            self.quit_requested.emit()

    def _set_animations(self, playing: bool) -> None:
        """Nothing animates while the window is hidden."""
        self.header.avatar.set_animated(playing)
        self.pill.set_animated(playing)

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._set_animations(True)
