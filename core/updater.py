"""Finding, fetching and applying new versions from GitHub Releases.

The rules that matter:

* only published releases with a real installer asset are ever offered
* nothing is downloaded or applied while a draft or a game is running
* the installer writes over the program files only -- settings live in
  %APPDATA% and are untouched by an update
"""

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

# States where an update must not interrupt: the user is drafting or playing.
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

# Inno Setup switches: no wizard, close and reopen the running app, no reboot.
INSTALL_SWITCHES = ("/SILENT", "/SP-", "/NOCANCEL", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS")

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class UpdateError(Exception):
    """Something went wrong that the user should be told about."""


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
    """True while an update would interrupt something that matters."""
    return str(state or "") in BUSY_STATES


def parse_releases(
    payload, current_version: str = __version__, *, allow_prerelease: bool = False
) -> Release | None:
    """The newest usable release that beats `current_version`, or None.

    Drafts, prereleases and releases without an installer are skipped rather
    than offered and then failing at download time.
    """
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
    """Ask GitHub whether there is anything newer. Raises UpdateError on trouble."""
    return parse_releases(
        fetch_releases(), current_version, allow_prerelease=allow_prerelease
    )


def download(release: Release, directory: Path | None = None, progress=None) -> Path:
    """Fetch the installer into a temporary folder and hand back the path."""
    target_dir = Path(directory or tempfile.gettempdir()) / "NeekoDraftAssistantUpdate"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UpdateError("Nowhere to put the download") from exc

    destination = target_dir / f"NeekoDraftAssistant-{release.version}{INSTALLER_SUFFIX}"
    request = urllib.request.Request(
        release.installer_url, headers={"User-Agent": "NeekoDraftAssistant"}
    )
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            total = release.size or int(response.headers.get("Content-Length") or 0)
            with open(destination, "wb") as handle:
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
    except UpdateError:
        raise
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateError("The download failed") from exc

    if release.size and written != release.size:
        raise UpdateError("The download came back the wrong size")
    return destination


def install(installer: Path) -> None:
    """Hand over to the installer, which closes this app and reopens the new one."""
    if not Path(installer).exists():
        raise UpdateError("The downloaded installer is missing")
    try:
        subprocess.Popen(
            [str(installer), *INSTALL_SWITCHES],
            creationflags=CREATE_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0),
            close_fds=True,
        )
    except OSError as exc:
        raise UpdateError("Windows would not start the installer") from exc


def running_as_installed_app() -> bool:
    """True in a packaged build; a source checkout cannot update itself."""
    return bool(getattr(sys, "frozen", False))


def settings_survive_update() -> bool:
    """The config must not live inside the program directory.

    An installer replaces its own folder wholesale, so anything kept there would
    be wiped on every update.
    """
    from core.settings import CONFIG_DIR

    if not running_as_installed_app():
        return True
    program_dir = Path(sys.executable).resolve().parent
    try:
        Path(CONFIG_DIR).resolve().relative_to(program_dir)
    except ValueError:
        return True
    return False
