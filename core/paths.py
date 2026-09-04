"""Where the app's own files live, in a checkout and in a packaged build.

PyInstaller unpacks the bundled data next to the executable and points
`sys._MEIPASS` at it, so resources have to be found through here rather than
relative to a source file.
"""

from __future__ import annotations

import sys
from pathlib import Path


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """The folder that holds `assets/`."""
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    return resource_root() / "assets"


def program_dir() -> Path:
    """Where the executable itself sits -- never a place to write settings."""
    if frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def launch_target() -> tuple[str, str]:
    """`(target, arguments)` for a shortcut that starts this app.

    A packaged build points straight at the executable; a checkout has to go
    through the windowed interpreter.
    """
    if frozen():
        return str(Path(sys.executable).resolve()), ""

    executable = Path(sys.executable)
    windowed = executable.with_name("pythonw.exe")
    interpreter = windowed if windowed.exists() else executable
    entry = Path(__file__).resolve().parent.parent / "main.py"
    return str(interpreter), f'"{entry}"'
