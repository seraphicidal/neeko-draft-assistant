"""Settings: a sidebar and one page at a time, deliberately unlike the dashboard."""

from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import startup
from core.settings import CONFIG_DIR, MAX_DELAY
from core.version import APP_NAME, GITHUB_URL, __version__
from ui import assets, theme
from ui.widgets import Hairline, Slider, SwitchRow, caption, label

SECTIONS = ["General", "Queue", "Champion select", "Chat", "Updates", "Advanced", "About"]


class SettingsWindow(QDialog):
    changed = Signal()
    check_updates = Signal()
    install_update = Signal()

    def __init__(self, settings, log, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.log = log
        self._building = True

        self.setWindowTitle(f"Settings - {APP_NAME}")
        self.resize(720, 560)
        self.setMinimumSize(660, 500)
        self.setStyleSheet(theme.stylesheet())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        self.pages = QStackedWidget()
        for builder in (
            self._page_general,
            self._page_queue,
            self._page_champion,
            self._page_chat,
            self._page_updates,
            self._page_advanced,
            self._page_about,
        ):
            self.pages.addWidget(self._scrollable(builder()))
        layout.addWidget(self.pages, 1)

        self.nav.setCurrentRow(0)
        self._building = False
        self.refresh_log()

    # -- chrome ------------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(178)
        panel.setStyleSheet(
            f"background: {theme.NAVY_850}; border-right: 1px solid {theme.LINE};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 18, 14, 16)
        layout.setSpacing(12)

        heading = label("Settings", "title")
        layout.addWidget(heading)

        self.nav = QListWidget()
        self.nav.setStyleSheet(
            f"""
            QListWidget {{ background: transparent; border: none; padding: 0; }}
            QListWidget::item {{ padding: 8px 10px; border-radius: 8px; color: {theme.MUTED}; }}
            QListWidget::item:hover {{ background: {theme.NAVY_800}; color: {theme.TEXT}; }}
            QListWidget::item:selected {{
                background: {theme.rgba(theme.ORANGE, 0.18)};
                color: {theme.CREAM};
                font-weight: 600;
            }}
            """
        )
        for name in SECTIONS:
            self.nav.addItem(QListWidgetItem(name))
        self.nav.currentRowChanged.connect(lambda index: self.pages.setCurrentIndex(index))
        layout.addWidget(self.nav, 1)

        layout.addWidget(label(f"v{__version__}", "small"))
        return panel

    def _scrollable(self, page: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidget(page)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setFrameShape(QFrame.Shape.NoFrame)
        return area

    def _page(self, title: str, blurb: str = "") -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(label(title, "title"))
        if blurb:
            note = label(blurb, "muted")
            note.setWordWrap(True)
            layout.addWidget(note)
        layout.addWidget(Hairline())
        return page, layout

    def _switch(self, layout: QVBoxLayout, text: str, attribute: str, note: str = "", on_change=None):
        control = SwitchRow(text, bool(getattr(self.settings, attribute)), note=note)

        def handler(value: bool) -> None:
            if self._building:
                return
            setattr(self.settings, attribute, value)
            self.settings.save()
            if on_change is not None:
                on_change(value)
            self.changed.emit()

        control.toggled.connect(handler)
        layout.addWidget(control)
        return control

    # -- pages --------------------------------------------------------------

    def _page_general(self) -> QWidget:
        page, layout = self._page("General", "How the app behaves on your desktop.")

        self.startup_row = SwitchRow(
            "Start with Windows", startup.is_enabled(),
            note="Adds a shortcut to your Startup folder.",
        )
        self.startup_row.toggled.connect(self._on_startup)
        layout.addWidget(self.startup_row)

        self._switch(layout, "Launch minimized", "launch_minimized",
                     "Start straight into the tray, without opening the window.")
        self._switch(layout, "Minimize to tray on close", "minimize_to_tray",
                     "Closing the window keeps Neeko watching in the background.")
        self._switch(layout, "Animations", "animations",
                     "Neeko's glow, the switches and the timer bar.")

        self.startup_note = label("", "danger")
        self.startup_note.hide()
        layout.addWidget(self.startup_note)
        layout.addStretch(1)
        return page

    def _page_queue(self) -> QWidget:
        page, layout = self._page("Queue", "What happens when a match is found.")
        self._switch(layout, "Auto accept queue", "auto_accept")

        layout.addSpacing(6)
        head = QHBoxLayout()
        head.addWidget(label("Accept delay", "body"))
        head.addStretch(1)
        self.delay_value = label("", "accent")
        head.addWidget(self.delay_value)
        layout.addLayout(head)

        self.delay_slider = Slider(self.settings.accept_delay, MAX_DELAY, 0.5)
        self.delay_slider.valueChanged.connect(self._on_delay)
        layout.addWidget(self.delay_slider)
        self._render_delay(self.settings.accept_delay)
        hint = label("A delay leaves you room to decline before Neeko presses accept.", "small")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addSpacing(6)
        self._switch(layout, "Sound on accept", "sound", "Two short tones when a queue is answered.")
        layout.addStretch(1)
        return page

    def _page_champion(self) -> QWidget:
        page, layout = self._page(
            "Champion select", "Neeko only ever acts when the client says it is your turn."
        )
        self._switch(layout, "Auto declare champion", "auto_declare",
                     "Hovers your champion so the team can see it. Commits to nothing.")
        self._switch(layout, "Auto lock in", "auto_pick",
                     "Locks the pick the moment it becomes yours. This cannot be undone.")

        layout.addSpacing(8)
        layout.addWidget(caption("Chosen champions"))
        self.champion_summary = label("", "muted")
        self.champion_summary.setWordWrap(True)
        layout.addWidget(self.champion_summary)
        layout.addWidget(label("Pick them in the main window.", "small"))
        layout.addStretch(1)
        return page

    def _page_chat(self) -> QWidget:
        page, layout = self._page("Chat", "One line, once per champion select.")
        self._switch(layout, "Send automatically", "chat_enabled")

        layout.addSpacing(6)
        layout.addWidget(caption("Message"))
        self.message_edit = QLineEdit(self.settings.chat_message)
        self.message_edit.setPlaceholderText("say something in champion select")
        self.message_edit.setMaxLength(200)
        self.message_edit.textChanged.connect(self._on_message)
        layout.addWidget(self.message_edit)
        note = label(
            "If it fails three times Neeko stops trying, so the chat is never spammed.", "small"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _page_updates(self) -> QWidget:
        page, layout = self._page("Updates", "New versions come from GitHub Releases.")

        version_row = QHBoxLayout()
        version_row.addWidget(label("Installed version", "body"))
        version_row.addStretch(1)
        version_row.addWidget(label(f"v{__version__}", "accent"))
        layout.addLayout(version_row)

        self.update_status = label("Not checked yet.", "muted")
        self.update_status.setWordWrap(True)
        layout.addWidget(self.update_status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.check_button = QPushButton("Check for updates")
        self.check_button.setObjectName("quiet")
        self.check_button.clicked.connect(self.check_updates.emit)
        buttons.addWidget(self.check_button)

        self.install_button = QPushButton("Update now")
        self.install_button.setObjectName("primary")
        self.install_button.clicked.connect(self.install_update.emit)
        self.install_button.hide()
        buttons.addWidget(self.install_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        layout.addSpacing(6)
        self._switch(layout, "Check automatically", "auto_check_updates",
                     "Once at startup, then every few hours. Never during a draft or a game.")

        layout.addSpacing(8)
        self.release_notes = QTextEdit()
        self.release_notes.setReadOnly(True)
        self.release_notes.setMinimumHeight(140)
        self.release_notes.setPlaceholderText("Release notes appear here.")
        layout.addWidget(self.release_notes, 1)
        return page

    def _page_advanced(self) -> QWidget:
        page, layout = self._page("Advanced", "For when something is not behaving.")

        level_row = QHBoxLayout()
        level_row.addWidget(label("Log level", "body"))
        level_row.addStretch(1)
        self.level_box = QComboBox()
        self.level_box.addItems(["Normal", "Debug"])
        self.level_box.setCurrentIndex(1 if self.settings.debug_logging else 0)
        self.level_box.currentIndexChanged.connect(self._on_level)
        level_row.addWidget(self.level_box)
        layout.addLayout(level_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(220)
        layout.addWidget(self.log_view, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        for text, handler in (
            ("Open config folder", self._open_config_folder),
            ("Refresh", self.refresh_log),
            ("Clear", self._clear_log),
        ):
            button = QPushButton(text)
            button.setObjectName("quiet")
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        return page

    def _page_about(self) -> QWidget:
        page, layout = self._page("About")

        layout.addWidget(label(APP_NAME, "display"))
        layout.addWidget(label(f"Version {__version__}", "accent"))
        made_for = label("Made for Miska.", "muted")
        layout.addWidget(made_for)

        link = QPushButton(GITHUB_URL)
        link.setObjectName("link")
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        layout.addWidget(link, 0, Qt.AlignmentFlag.AlignLeft)

        layout.addSpacing(10)
        layout.addWidget(caption("Neeko art"))
        intro = label(
            f"Drop your own pictures into {assets.NEEKO.name}\\ next to the app and restart. "
            "Missing files fall back to what ships with the assistant.",
            "small",
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        for slots, name, purpose in assets.SLOT_HELP:
            present = assets.first_existing(slots)
            mark = "✓" if present else "·"
            entry = label(f"   {mark}  {name} — {purpose}", "small")
            entry.setStyleSheet(
                f"color: {theme.SUCCESS if present else theme.DIM}; font-size: 11px;"
            )
            entry.setWordWrap(True)
            layout.addWidget(entry)

        layout.addStretch(1)
        return page

    # -- handlers ------------------------------------------------------------

    def _render_delay(self, value: float) -> None:
        self.delay_value.setText("instantly" if value == 0 else f"{value:.1f}s")

    def _on_delay(self, value: float) -> None:
        self._render_delay(value)
        if self._building:
            return
        self.settings.accept_delay = value
        self.settings.save()
        self.changed.emit()

    def _on_message(self, text: str) -> None:
        if self._building:
            return
        self.settings.chat_message = text
        self.settings.save()
        self.changed.emit()

    def _on_startup(self, wanted: bool) -> None:
        if self._building:
            return
        if startup.set_enabled(wanted):
            self.startup_note.hide()
            return
        self.startup_row.setChecked(not wanted)
        self.startup_note.setText("Windows would not let us change the startup entry.")
        self.startup_note.show()

    def _on_level(self, index: int) -> None:
        if self._building:
            return
        self.settings.debug_logging = index == 1
        self.log.debug_enabled = self.settings.debug_logging
        self.settings.save()
        self.changed.emit()

    def _open_config_folder(self) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(CONFIG_DIR)  # noqa: S606 - opening the user's own folder
            else:
                subprocess.Popen(["xdg-open", str(CONFIG_DIR)])
        except OSError:
            pass

    def _clear_log(self) -> None:
        self.log.clear()
        self.refresh_log()

    # -- live views ------------------------------------------------------------

    def refresh_log(self) -> None:
        self.log_view.setPlainText(self.log.as_text())
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def append_log(self, text: str) -> None:
        if not self.isVisible():
            return
        self.log_view.append(text)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def show_update_state(self, text: str, tint: str = theme.MUTED, release=None) -> None:
        self.update_status.setText(text)
        self.update_status.setStyleSheet(f"color: {tint}; font-size: 12px;")
        self.install_button.setVisible(release is not None)
        if release is not None and release.notes:
            self.release_notes.setPlainText(release.notes)

    def set_checking(self, busy: bool) -> None:
        self.check_button.setEnabled(not busy)
        self.check_button.setText("Checking..." if busy else "Check for updates")

    def sync_from_settings(self) -> None:
        self._building = True
        preferred = self.settings.preferred_champion_name or "nobody yet"
        backup = self.settings.backup_champion_name or "none"
        self.champion_summary.setText(f"Preferred: {preferred}\nBackup: {backup}")
        self.message_edit.setText(self.settings.chat_message)
        self.delay_slider.setValue(self.settings.accept_delay)
        self._render_delay(self.settings.accept_delay)
        self.level_box.setCurrentIndex(1 if self.settings.debug_logging else 0)
        self._building = False
