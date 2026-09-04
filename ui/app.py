"""Wiring: settings, catalog, watcher, art, updates, window and tray.

The watcher and the art loader run on their own threads and report through Qt
signals, which is how their events cross safely onto the GUI thread.
"""

from __future__ import annotations

import sys
import threading
import webbrowser

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core import updater
from core.logbook import LogBook
from core.settings import Settings
from core.version import APP_NAME, GITHUB_URL, __version__
from core.watcher import Watcher
from league.champions import Catalog
from ui import assets, theme
from ui.art_loader import ArtLoader
from ui.main_window import MainWindow
from ui.settings_window import SettingsWindow
from ui.tray import Tray

FIRST_CHECK_MS = 20_000
RECHECK_MS = 6 * 60 * 60 * 1000


class EventBridge(QObject):
    """Watcher events, and the results of background update work."""

    event = Signal(str, dict)
    update_checked = Signal(object, str)
    update_downloaded = Signal(object, str)


class Application:
    def __init__(self, argv: list[str] | None = None) -> None:
        self.qt = QApplication(argv if argv is not None else sys.argv)
        self.qt.setApplicationName(APP_NAME)
        self.qt.setApplicationVersion(__version__)
        self.qt.setWindowIcon(QIcon(str(assets.ICON)))
        self.qt.setStyleSheet(theme.stylesheet())
        self.qt.setQuitOnLastWindowClosed(False)

        self.settings = Settings.load()
        self.log = LogBook()
        self.log.debug_enabled = self.settings.debug_logging
        self.catalog = Catalog.bundled()

        self.bridge = EventBridge()
        self.bridge.event.connect(self._on_event)
        self.bridge.update_checked.connect(self._on_update_checked)
        self.bridge.update_downloaded.connect(self._on_update_downloaded)

        self.watcher = Watcher(self.settings, self.catalog, self.log, self.bridge.event.emit)
        self.art = ArtLoader(self.catalog)
        self.art.loaded.connect(self._on_art)

        self.window = MainWindow(self.settings, self.catalog)
        self.window.quit_requested.connect(self.quit)
        self.window.settings_requested.connect(self.open_settings)
        self.window.pause_toggled.connect(self._on_pause)
        self.window.art_wanted.connect(self.art.request)
        self.window.update_requested.connect(self.start_update)

        self.settings_window: SettingsWindow | None = None
        self.pending_update = None
        self._checking = False

        self.tray = Tray(self.settings)
        self.tray.open_requested.connect(self.window.show_window)
        self.tray.settings_requested.connect(self.open_settings)
        self.tray.quit_requested.connect(self.quit)
        self.tray.pause_toggled.connect(self._on_tray_pause)
        self.tray.setting_toggled.connect(self._on_tray_setting)
        self.tray.show()

        self._update_timer = QTimer(self.qt)
        self._update_timer.timeout.connect(lambda: self.check_updates(manual=False))

    # -- lifecycle ---------------------------------------------------------

    def run(self) -> int:
        self.watcher.start()
        self.art.start()
        self.window.request_art()

        if self.settings.launch_minimized:
            self.tray.notify("Neeko is watching your queue from here.")
        else:
            self.window.show()

        if self.settings.auto_check_updates:
            QTimer.singleShot(FIRST_CHECK_MS, lambda: self.check_updates(manual=False))
            self._update_timer.start(RECHECK_MS)
        return self.qt.exec()

    def quit(self) -> None:
        self.settings.save()
        self.watcher.stop()
        self.art.stop()
        self.tray.hide()
        self.qt.quit()

    def open_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.settings, self.log, None)
            self.settings_window.changed.connect(self._on_settings_changed)
            self.settings_window.check_updates.connect(lambda: self.check_updates(manual=True))
            self.settings_window.install_update.connect(self.start_update)
        self.settings_window.sync_from_settings()
        self.settings_window.refresh_log()
        if self.pending_update is not None:
            self.settings_window.show_update_state(
                f"Version {self.pending_update.version} is ready to install.",
                theme.ACCENT,
                self.pending_update,
            )
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    # -- watcher events -----------------------------------------------------

    def _on_event(self, kind: str, payload: dict) -> None:
        if kind == "status":
            status = payload["status"]
            self.window.apply_status(status)
            self.tray.set_status(status.connected, status.detail)
        elif kind == "action":
            self.window.show_action(payload["text"], payload["level"])
            self.tray.notify(payload["text"])
            if payload.get("chime"):
                self._beep()
        elif kind == "log":
            if self.settings_window is not None:
                entries = self.log.entries()
                if entries:
                    self.settings_window.append_log(str(entries[-1]))
        elif kind == "counters":
            self.window.refresh_counters()
        elif kind == "catalog":
            # The client can serve art now, so let previously failed art retry.
            self.art.forget(self.settings.preferred_champion_id)
            self.art.forget(self.settings.backup_champion_id)
            self.window.refresh_names_from_catalog()

    def _on_art(self, kind: str, champion_id: int, data: bytes) -> None:
        self.window.set_art(kind, champion_id, data)

    # -- settings -----------------------------------------------------------

    def _on_settings_changed(self) -> None:
        self.window._load_from_settings()
        self.log.debug_enabled = self.settings.debug_logging
        self.tray.sync()

    def _on_tray_setting(self, attribute: str, value: bool) -> None:
        setattr(self.settings, attribute, value)
        self.settings.save()
        self.window._load_from_settings()
        if self.settings_window is not None:
            self.settings_window.sync_from_settings()

    def _on_pause(self, paused: bool) -> None:
        self.watcher.paused = paused
        self.tray.set_paused(paused)

    def _on_tray_pause(self, paused: bool) -> None:
        self.watcher.paused = paused
        self.window.pause_button.blockSignals(True)
        self.window.pause_button.setChecked(paused)
        self.window.pause_button.setText("Paused" if paused else "Pause")
        self.window.pause_button.blockSignals(False)
        self.tray.notify("Paused - Neeko will not answer anything." if paused else "Back on duty.")

    # -- updates --------------------------------------------------------------

    @property
    def busy_state(self) -> str:
        return self.watcher.machine.state.value

    def check_updates(self, manual: bool = False) -> None:
        if self._checking:
            return
        if not manual and updater.is_busy(self.busy_state):
            return  # never interrupt a draft or a game with an update prompt
        self._checking = True
        if self.settings_window is not None:
            self.settings_window.set_checking(True)

        def work() -> None:
            try:
                release = updater.check(__version__)
                self.bridge.update_checked.emit(release, "")
            except updater.UpdateError as exc:
                self.bridge.update_checked.emit(None, str(exc))

        threading.Thread(target=work, name="neeko-update-check", daemon=True).start()

    def _on_update_checked(self, release, error: str) -> None:
        self._checking = False
        if self.settings_window is not None:
            self.settings_window.set_checking(False)

        if error:
            self.log.add("warn", f"Update check failed: {error}")
            if self.settings_window is not None:
                self.settings_window.show_update_state(error, theme.WARNING)
            return

        if release is None:
            self.log.add("debug", "Update check: already current")
            if self.settings_window is not None:
                self.settings_window.show_update_state(
                    "You're up to date.", theme.SUCCESS
                )
            return

        self.pending_update = release
        self.log.add("info", f"Update available: {release.version}")
        if self.settings_window is not None:
            self.settings_window.show_update_state(
                f"Version {release.version} is available.", theme.ACCENT, release
            )
        if not updater.is_busy(self.busy_state):
            self.window.offer_update(release)
            self.tray.notify(f"Neeko found version {release.version}!")

    def start_update(self) -> None:
        release = self.pending_update
        if release is None:
            return
        if updater.is_busy(self.busy_state):
            self.window.update_progress("Neeko will wait until you're out of the game.")
            return
        if not updater.running_as_installed_app():
            # A source checkout has nothing for the installer to replace.
            webbrowser.open(f"{GITHUB_URL}/releases/latest")
            self.window.update_progress("Opened the release page in your browser.")
            return

        self.window.update_progress(f"Downloading version {release.version}...")

        def work() -> None:
            try:
                path = updater.download(release)
                self.bridge.update_downloaded.emit(path, "")
            except updater.UpdateError as exc:
                self.bridge.update_downloaded.emit(None, str(exc))

        threading.Thread(target=work, name="neeko-update-download", daemon=True).start()

    def _on_update_downloaded(self, path, error: str) -> None:
        if error or path is None:
            self.log.add("warn", f"Update download failed: {error}")
            self.window.update_progress(f"Update failed: {error}")
            return
        if updater.is_busy(self.busy_state):
            self.window.update_progress("Update ready - Neeko will wait until after the game.")
            return
        try:
            updater.install(path)
        except updater.UpdateError as exc:
            self.window.update_progress(f"Update failed: {exc}")
            return
        self.log.add("info", "Handing over to the installer")
        self.quit()

    # -- feedback --------------------------------------------------------------

    def _beep(self) -> None:
        if not self.settings.sound or sys.platform != "win32":
            return

        def play() -> None:
            try:
                import winsound

                winsound.Beep(988, 90)
                winsound.Beep(1319, 130)
            except Exception:  # a missing beep is not worth an error
                pass

        threading.Thread(target=play, daemon=True).start()


def main() -> int:
    if sys.platform != "win32":
        print("Neeko's Draft Assistant talks to the Windows League client only.")
        return 1
    return Application().run()
