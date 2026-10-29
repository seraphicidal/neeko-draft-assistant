
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from league.lcu_client import CREATE_NO_WINDOW

APP_NAME = "Neeko Draft Assistant"
LEGACY_NAME = "Queue Auto-Accept"

from core.paths import assets_dir, launch_target, program_dir

_ICON = assets_dir() / "icon.ico"


def startup_dir() -> Path:
    return (
        Path(os.environ.get("APPDATA", Path.home()))
        / "Microsoft/Windows/Start Menu/Programs/Startup"
    )


def shortcut_path() -> Path:
    return startup_dir() / f"{APP_NAME}.lnk"


def is_enabled() -> bool:
    return shortcut_path().exists()


def _registry_command() -> str:
    target, arguments = launch_target()
    return f'"{target}" {arguments}'.strip()


def is_enabled() -> bool:
    if shortcut_path().exists():
        return True
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except (OSError, FileNotFoundError):
        return False


def enable() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _registry_command())
        shortcut_path().unlink(missing_ok=True)
        (startup_dir() / f"{LEGACY_NAME}.lnk").unlink(missing_ok=True)
        return is_enabled()
    except OSError:
        return False


def disable() -> bool:
    try:
        shortcut_path().unlink(missing_ok=True)
        (startup_dir() / f"{LEGACY_NAME}.lnk").unlink(missing_ok=True)
    except OSError:
        pass
    if sys.platform != "win32":
        return True
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        return not is_enabled()
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    return enable() if enabled else disable()
