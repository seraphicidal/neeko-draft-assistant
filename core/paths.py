
from __future__ import annotations

import sys
from pathlib import Path


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    return resource_root() / "assets"


def program_dir() -> Path:
    if frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def launch_target() -> tuple[str, str]:
    if frozen():
        return str(Path(sys.executable).resolve()), ""

    executable = Path(sys.executable)
    windowed = executable.with_name("pythonw.exe")
    interpreter = windowed if windowed.exists() else executable
    entry = Path(__file__).resolve().parent.parent / "main.py"
    return str(interpreter), f'"{entry}"'
