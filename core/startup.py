"""Run at login, via a shortcut in the user's Startup folder.

A shortcut (rather than a registry Run entry) keeps this visible and removable
from Task Manager's Startup tab, and points at pythonw.exe so nothing flashes
a console at login.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from league.lcu_client import CREATE_NO_WINDOW

APP_NAME = "Neeko Draft Assistant"
LEGACY_NAME = "Queue Auto-Accept"  # the shortcut the queue-only build made

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


def _ps_literal(value) -> str:
    """A PowerShell single-quoted string. Nothing inside is expanded."""
    return "'" + str(value).replace("'", "''") + "'"


def enable() -> bool:
    """Create the Startup shortcut. Returns False if Windows refused."""
    target, arguments = launch_target()
    script = "; ".join(
        [
            "$shell = New-Object -ComObject WScript.Shell",
            f"$link = $shell.CreateShortcut({_ps_literal(shortcut_path())})",
            f"$link.TargetPath = {_ps_literal(target)}",
            f"$link.Arguments = {_ps_literal(arguments)}",
            f"$link.WorkingDirectory = {_ps_literal(program_dir())}",
            f"$link.IconLocation = {_ps_literal(_ICON)}",
            f"$link.Description = {_ps_literal('Neeko draft assistant for League of Legends')}",
            "$link.Save()",
        ]
    )
    try:
        startup_dir().mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return is_enabled()


def disable() -> bool:
    try:
        shortcut_path().unlink(missing_ok=True)
        (startup_dir() / f"{LEGACY_NAME}.lnk").unlink(missing_ok=True)
    except OSError:
        return False
    return not is_enabled()


def set_enabled(enabled: bool) -> bool:
    return enable() if enabled else disable()
