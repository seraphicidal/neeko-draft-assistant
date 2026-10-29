
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from core.version import (
    INSTALLER_SUFFIX,
    RELEASES_API,
    __version__,
    version_tuple,
)

TIMEOUT = 12.0
MAX_INSTALLER_BYTES = 200 * 1024 * 1024

BUSY_STATES = frozenset(
    {
        "READY_CHECK",
        "ACCEPTED",
        "CHAMP_SELECT",
        "WAITING_FOR_MY_TURN",
        "MY_TURN",
        "LOCKED",
        "IN_GAME",
    }
)

INSTALL_SWITCHES = ("/SILENT", "/SP-", "/NOCANCEL", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS")

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class Release:
    version: str
    tag: str
    name: str
    notes: str
    installer_url: str
    size: int = 0

    @property
    def title(self) -> str:
        return self.name or f"Version {self.version}"


def is_busy(state: str | None) -> bool:
    return str(state or "") in BUSY_STATES


def parse_releases(
    payload, current_version: str = __version__, *, allow_prerelease: bool = False
) -> Release | None:
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise UpdateError("GitHub returned something that is not a release list")

    current = version_tuple(current_version)
    best: Release | None = None

    for entry in payload:
        if not isinstance(entry, dict):
            continue
        if entry.get("draft"):
            continue
        if entry.get("prerelease") and not allow_prerelease:
            continue

        tag = str(entry.get("tag_name") or "")
        if not tag:
            continue
        version = version_tuple(tag)
        if version <= current:
            continue
        if best is not None and version <= version_tuple(best.version):
            continue

        installer = _installer_asset(entry.get("assets"))
        if installer is None:
            continue

        best = Release(
            version=tag.lstrip("vV"),
            tag=tag,
            name=str(entry.get("name") or ""),
            notes=str(entry.get("body") or "").strip(),
            installer_url=installer[0],
            size=installer[1],
        )
    return best


def _installer_asset(assets) -> tuple[str, int] | None:
    for asset in assets or []:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if name.endswith(INSTALLER_SUFFIX) and url:
            try:
                size = int(asset.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            return url, size
    return None


def fetch_releases(timeout: float = TIMEOUT) -> list:
    request = urllib.request.Request(
        RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "NeekoDraftAssistant",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub said {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateError("Could not reach GitHub") from exc
    except ValueError as exc:
        raise UpdateError("GitHub sent a broken answer") from exc


def check(
    current_version: str = __version__, *, allow_prerelease: bool = False
) -> Release | None:
    return parse_releases(
        fetch_releases(), current_version, allow_prerelease=allow_prerelease
    )


def download(release: Release, directory: Path | None = None, progress=None) -> Path:
    target_dir = Path(directory or tempfile.gettempdir()) / "NeekoDraftAssistantUpdate"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UpdateError("Nowhere to put the download") from exc

    destination = target_dir / f"NeekoDraftAssistant-{release.version}{INSTALLER_SUFFIX}"
    part_file = destination.with_suffix(".part")
    request = urllib.request.Request(
        release.installer_url, headers={"User-Agent": "NeekoDraftAssistant"}
    )
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            total = release.size or int(response.headers.get("Content-Length") or 0)
            with open(part_file, "wb") as handle:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_INSTALLER_BYTES:
                        raise UpdateError("The download is implausibly large")
                    handle.write(chunk)
                    if progress is not None and total:
                        progress(min(1.0, written / total))
        if release.size and written != release.size:
            raise UpdateError("The download came back the wrong size")
        os.replace(part_file, destination)
    except UpdateError:
        part_file.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError) as exc:
        part_file.unlink(missing_ok=True)
        raise UpdateError("The download failed") from exc

    return destination


def install(installer: Path) -> None:
    installer_path = Path(installer).resolve()
    if not installer_path.exists():
        raise UpdateError("The downloaded installer is missing")
    try:
        if sys.platform == "win32":
            switches = " ".join(INSTALL_SWITCHES)
            cmd = f'cmd.exe /c "ping 127.0.0.1 -n 2 >nul & "{installer_path}" {switches}"'
            subprocess.Popen(
                cmd,
                creationflags=CREATE_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0),
                close_fds=True,
            )
        else:
            subprocess.Popen(
                [str(installer_path), *INSTALL_SWITCHES],
                close_fds=True,
            )
    except OSError as exc:
        raise UpdateError("Windows would not start the installer") from exc


def running_as_installed_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def settings_survive_update() -> bool:
    from core.settings import CONFIG_DIR

    if not running_as_installed_app():
        return True
    program_dir = Path(sys.executable).resolve().parent
    try:
        Path(CONFIG_DIR).resolve().relative_to(program_dir)
    except ValueError:
        return True
    return False
