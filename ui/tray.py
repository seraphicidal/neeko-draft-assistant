
from __future__ import annotations

import sys

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from core.version import APP_NAME, __version__
from ui import assets

TITLE = APP_NAME


def _sync_windows_tray_cache() -> None:
    if sys.platform != "win32":
        return
    try:
        from pathlib import Path
        import winreg

        png_path = assets.ICON_PNG
        if not Path(png_path).exists():
            return
        data = Path(png_path).read_bytes()
        key_path = r"Control Panel\NotifyIconSettings"
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE
        ) as parent:
            count, _, _ = winreg.QueryInfoKey(parent)
            for index in range(count):
                try:
                    sub_name = winreg.EnumKey(parent, index)
                    with winreg.OpenKey(
                        parent, sub_name, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
                    ) as sub:
                        exe, _ = winreg.QueryValueEx(sub, "ExecutablePath")
                        if "neekodraftassistant" in str(exe).lower():
                            winreg.SetValueEx(sub, "IconSnapshot", 0, winreg.REG_BINARY, data)
                except OSError:
                    continue
    except Exception:
        pass


class Tray(QSystemTrayIcon):
    open_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    pause_toggled = Signal(bool)
    setting_toggled = Signal(str, bool)

    def __init__(self, settings, parent=None) -> None:
        _sync_windows_tray_cache()
        super().__init__(assets.app_icon(), parent)
        self.settings = settings
        self.setToolTip(TITLE)

        menu = QMenu()

        header = QAction(f"{TITLE}  ·  v{__version__}", menu)
        header.setEnabled(False)
        menu.addAction(header)

        self.status_action = QAction("Waiting for League Client...", menu)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        menu.addSeparator()

        self.accept_action = self._switch(menu, "Auto Accept", "auto_accept")
        self.declare_action = self._switch(menu, "Auto Declare", "auto_declare")
        self.pick_action = self._switch(menu, "Auto Pick", "auto_pick")
        self.ban_action = self._switch(menu, "Auto Ban", "auto_ban")
        self.chat_action = self._switch(menu, "Auto Chat", "chat_enabled")
        menu.addSeparator()

        open_action = QAction("Open App", menu)
        open_action.triggered.connect(self.open_requested.emit)
        menu.addAction(open_action)

        settings_action = QAction("Settings", menu)
        settings_action.triggered.connect(self.settings_requested.emit)
        menu.addAction(settings_action)

        self.pause_action = QAction("Pause", menu)
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.pause_toggled.emit)
        menu.addAction(self.pause_action)
        menu.addSeparator()

        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(exit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        self._menu = menu

    def _switch(self, menu: QMenu, text: str, attribute: str) -> QAction:
        action = QAction(text, menu)
        action.setCheckable(True)
        action.setChecked(bool(getattr(self.settings, attribute)))
        action.toggled.connect(lambda value: self.setting_toggled.emit(attribute, value))
        menu.addAction(action)
        return action

    def _on_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self.open_requested.emit()

    def sync(self) -> None:
        for action, attribute in (
            (self.accept_action, "auto_accept"),
            (self.declare_action, "auto_declare"),
            (self.pick_action, "auto_pick"),
            (self.ban_action, "auto_ban"),
            (self.chat_action, "chat_enabled"),
        ):
            wanted = bool(getattr(self.settings, attribute))
            if action.isChecked() != wanted:
                action.blockSignals(True)
                action.setChecked(wanted)
                action.blockSignals(False)

    def set_paused(self, paused: bool) -> None:
        if self.pause_action.isChecked() == paused:
            return
        self.pause_action.blockSignals(True)
        self.pause_action.setChecked(paused)
        self.pause_action.blockSignals(False)

    def set_status(self, connected: bool, detail: str) -> None:
        mark = "●" if connected else "○"
        self.status_action.setText(f"{mark} {detail}")
        self.setToolTip(f"{TITLE}\n{detail}")

    def notify(self, text: str) -> None:
        self.showMessage(TITLE, text, QIcon(str(assets.ICON)), 4000)
