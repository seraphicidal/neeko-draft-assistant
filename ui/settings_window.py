"""Settings: a sidebar, one page at a time, every row explaining itself.

Deliberately a different shape from the dashboard -- this is where you configure
the app, not where you watch it work.
"""

from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
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
from ui.widgets import Divider, SettingRow, Slider, caption, text

SECTIONS = ["General", "Queue", "Champion select", "Draft chat", "Updates", "Advanced", "About"]


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
        self.resize(740, 580)
        self.setMinimumSize(680, 520)
        self.setStyleSheet(theme.stylesheet())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # The sidebar wires itself to the page stack, so the stack has to exist
        # before the sidebar is built.
        self.pages = QStackedWidget()
        layout.addWidget(self._build_sidebar())

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

    # -------------------------------------------------------------- chrome ---

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(186)
        panel.setStyleSheet(
            f"background: {theme.SURFACE}; border-right: 1px solid {theme.BORDER};"
        )
        column = QVBoxLayout(panel)
        column.setContentsMargins(theme.SPACE_3, theme.SPACE_5, theme.SPACE_3, theme.SPACE_4)
        column.setSpacing(theme.SPACE_4)
        column.addWidget(text("Settings", "title"))

        self.nav = QListWidget()
        self.nav.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.nav.setStyleSheet(
            f"""
            QListWidget {{ background: transparent; border: none; }}
            QListWidget::item {{
                padding: 9px 11px; border-radius: {theme.RADIUS_SM}px;
                color: {theme.TEXT_SECONDARY};
            }}
            QListWidget::item:hover {{ background: {theme.SURFACE_HOVER};
                                       color: {theme.TEXT_PRIMARY}; }}
            QListWidget::item:selected {{
                background: {theme.rgba(theme.ACCENT, 0.16)};
                color: {theme.TEXT_PRIMARY};
                font-weight: 600;
            }}
            """
        )
        for name in SECTIONS:
            self.nav.addItem(QListWidgetItem(name))
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        column.addWidget(self.nav, 1)
        column.addWidget(text(f"v{__version__}", "small"))
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
        column = QVBoxLayout(page)
        column.setContentsMargins(theme.SPACE_6, theme.SPACE_6, theme.SPACE_6, theme.SPACE_6)
        column.setSpacing(theme.SPACE_2)
        column.addWidget(text(title, "title"))
        if blurb:
            note = text(blurb, "secondary")
            note.setWordWrap(True)
            column.addWidget(note)
        column.addSpacing(theme.SPACE_2)
        column.addWidget(Divider())
        return page, column

    def _row(self, column: QVBoxLayout, title: str, description: str, attribute: str,
             on_change=None) -> SettingRow:
        control = SettingRow(title, description, bool(getattr(self.settings, attribute)))

        def handler(value: bool) -> None:
            if self._building:
                return
            setattr(self.settings, attribute, value)
            self.settings.save()
            if on_change is not None:
                on_change(value)
            self.changed.emit()

        control.toggled.connect(handler)
        column.addWidget(control)
        return control

    # --------------------------------------------------------------- pages ---

    def _page_general(self) -> QWidget:
        page, column = self._page("General", "How the app behaves on your desktop.")

        self.startup_row = SettingRow(
            "Start with Windows",
            "Adds a shortcut to your Startup folder.",
            startup.is_enabled(),
        )
        self.startup_row.toggled.connect(self._on_startup)
        column.addWidget(self.startup_row)

        self._row(column, "Launch minimized",
                  "Start straight into the tray without opening the window.",
                  "launch_minimized")
        self._row(column, "Minimize to tray on close",
                  "Closing the window keeps Neeko watching in the background.",
                  "minimize_to_tray")
        self._row(column, "Animations",
                  "Neeko's idle motion, the switches and the status dot.",
                  "animations")

        self.startup_note = text("", "error")
        self.startup_note.hide()
        column.addWidget(self.startup_note)
        column.addStretch(1)
        return page

    def _page_queue(self) -> QWidget:
        page, column = self._page("Queue", "What happens when a match is found.")
        self._row(column, "Auto accept", "Answer the ready check for you.", "auto_accept")

        column.addSpacing(theme.SPACE_3)
        head = QHBoxLayout()
        head.addWidget(text("Accept after", "body-strong"), 1)
        self.delay_value = text("", "accent")
        head.addWidget(self.delay_value)
        column.addLayout(head)

        self.delay_slider = Slider(self.settings.accept_delay, MAX_DELAY, 0.5)
        self.delay_slider.valueChanged.connect(self._on_delay)
        column.addWidget(self.delay_slider)

        scale = QHBoxLayout()
        scale.addWidget(text("0s", "small"))
        scale.addStretch(1)
        scale.addWidget(text(f"{MAX_DELAY:.0f}s", "small"))
        column.addLayout(scale)
        self._render_delay(self.settings.accept_delay)

        hint = text("A delay leaves you room to decline before Neeko presses accept.", "small")
        hint.setWordWrap(True)
        column.addWidget(hint)

        column.addSpacing(theme.SPACE_3)
        self._row(column, "Sound on accept", "Two short tones when a queue is answered.", "sound")
        column.addStretch(1)
        return page

    def _page_champion(self) -> QWidget:
        page, column = self._page(
            "Champion select",
            "Neeko only ever acts when the client says the action is yours.",
        )
        self._row(column, "Auto declare",
                  "Hover your champion so the team can see it. Commits to nothing.",
                  "auto_declare")
        self._row(column, "Auto lock-in",
                  "Lock the pick in the moment it becomes yours. This cannot be undone.",
                  "auto_pick")

        column.addSpacing(theme.SPACE_3)
        column.addWidget(caption("Chosen champions"))
        self.champion_summary = text("", "secondary")
        self.champion_summary.setWordWrap(True)
        column.addWidget(self.champion_summary)
        column.addWidget(text("Pick them on the dashboard.", "small"))
        column.addStretch(1)
        return page

    def _page_chat(self) -> QWidget:
        page, column = self._page("Draft chat", "One line, once per champion select.")
        self._row(column, "Send automatically",
                  "Posted as soon as the draft chat room opens.", "chat_enabled")

        column.addSpacing(theme.SPACE_3)
        column.addWidget(caption("Message"))
        self.message_edit = QLineEdit(self.settings.chat_message)
        self.message_edit.setPlaceholderText("Say something in champion select")
        self.message_edit.setMaxLength(200)
        self.message_edit.textChanged.connect(self._on_message)
        column.addWidget(self.message_edit)

        note = text(
            "If it fails three times Neeko stops trying, so the chat is never spammed.",
            "small",
        )
        note.setWordWrap(True)
        column.addWidget(note)
        column.addStretch(1)
        return page

    def _page_updates(self) -> QWidget:
        page, column = self._page("Updates", "New versions come from GitHub Releases.")

        installed = QHBoxLayout()
        installed.addWidget(text("Installed version", "body-strong"), 1)
        installed.addWidget(text(f"v{__version__}", "accent"))
        column.addLayout(installed)

        self.update_status = text("Not checked yet.", "secondary")
        self.update_status.setWordWrap(True)
        column.addWidget(self.update_status)

        column.addSpacing(theme.SPACE_2)
        buttons = QHBoxLayout()
        buttons.setSpacing(theme.SPACE_2)
        self.check_button = QPushButton("Check for updates")
        self.check_button.clicked.connect(self.check_updates.emit)
        buttons.addWidget(self.check_button)

        self.install_button = QPushButton("Update now")
        self.install_button.setObjectName("primary")
        self.install_button.clicked.connect(self.install_update.emit)
        self.install_button.hide()
        buttons.addWidget(self.install_button)
        buttons.addStretch(1)
        column.addLayout(buttons)

        column.addSpacing(theme.SPACE_2)
        self._row(column, "Check automatically",
                  "Once at startup, then every few hours. Never during a draft or a game.",
                  "auto_check_updates")

        column.addSpacing(theme.SPACE_2)
        column.addWidget(caption("Release notes"))
        self.release_notes = QTextEdit()
        self.release_notes.setReadOnly(True)
        self.release_notes.setMinimumHeight(130)
        self.release_notes.setPlaceholderText("Notes for the next version appear here.")
        column.addWidget(self.release_notes, 1)
        return page

    def _page_advanced(self) -> QWidget:
        page, column = self._page("Advanced", "For when something is not behaving.")

        level = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(1)
        names.addWidget(text("Log level", "body-strong"))
        names.addWidget(text("Debug records every state change and request.", "small"))
        level.addLayout(names, 1)
        self.level_box = QComboBox()
        self.level_box.addItems(["Normal", "Debug"])
        self.level_box.setCurrentIndex(1 if self.settings.debug_logging else 0)
        self.level_box.currentIndexChanged.connect(self._on_level)
        level.addWidget(self.level_box)
        column.addLayout(level)

        column.addSpacing(theme.SPACE_3)
        column.addWidget(caption("Activity log"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(210)
        column.addWidget(self.log_view, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(theme.SPACE_2)
        buttons.addStretch(1)
        for title, handler in (
            ("Open config folder", self._open_config_folder),
            ("Refresh", self.refresh_log),
            ("Clear", self._clear_log),
        ):
            button = QPushButton(title)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        column.addLayout(buttons)
        return page

    def _page_about(self) -> QWidget:
        page, column = self._page("About")
        column.addWidget(text(APP_NAME, "display"))
        column.addWidget(text(f"Version {__version__}", "accent"))
        column.addWidget(text("Made for Miska.", "secondary"))

        link = QPushButton(GITHUB_URL)
        link.setObjectName("link")
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        column.addWidget(link, 0, Qt.AlignmentFlag.AlignLeft)

        column.addSpacing(theme.SPACE_4)
        column.addWidget(caption("Neeko art"))
        intro = text(
            "Drop your own pictures into the neeko folder beside the app and restart. "
            "Anything missing falls back to what ships with the assistant.",
            "small",
        )
        intro.setWordWrap(True)
        column.addWidget(intro)

        for filename, purpose, present in assets.slot_help():
            mark = "✓" if present else "·"
            entry = text(f"   {mark}  {filename} — {purpose}", "small")
            entry.setStyleSheet(
                theme.font_css("small", theme.SUCCESS if present else theme.TEXT_MUTED)
            )
            entry.setWordWrap(True)
            column.addWidget(entry)
        column.addStretch(1)
        return page

    # ------------------------------------------------------------ handlers ---

    def _render_delay(self, value: float) -> None:
        self.delay_value.setText("instantly" if value == 0 else f"{value:.1f} seconds")

    def _on_delay(self, value: float) -> None:
        self._render_delay(value)
        if self._building:
            return
        self.settings.accept_delay = value
        self.settings.save()
        self.changed.emit()

    def _on_message(self, value: str) -> None:
        if self._building:
            return
        self.settings.chat_message = value
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
                os.startfile(CONFIG_DIR)  # noqa: S606 - the user's own folder
            else:
                subprocess.Popen(["xdg-open", str(CONFIG_DIR)])
        except OSError:
            pass

    def _clear_log(self) -> None:
        self.log.clear()
        self.refresh_log()

    # ---------------------------------------------------------- live views ---

    def refresh_log(self) -> None:
        self.log_view.setPlainText(self.log.as_text())
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def append_log(self, line: str) -> None:
        if not self.isVisible():
            return
        self.log_view.append(line)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def show_update_state(self, message: str, tone: str = theme.TEXT_SECONDARY, release=None) -> None:
        self.update_status.setText(message)
        self.update_status.setStyleSheet(theme.font_css("secondary", tone))
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
        self.champion_summary.setText(f"Primary: {preferred}\nBackup: {backup}")
        self.message_edit.setText(self.settings.chat_message)
        self.delay_slider.setValue(self.settings.accept_delay)
        self._render_delay(self.settings.accept_delay)
        self.level_box.setCurrentIndex(1 if self.settings.debug_logging else 0)
        self._building = False
