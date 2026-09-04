"""Finding the local League client and talking to it.

The client runs a small HTTPS server on 127.0.0.1 and hands out a fresh port and
password every time it starts. Credentials come from its `lockfile`, or from the
process command line when the file is missing.

Grown out of the original auto-accept client: the `(status, body)` contract and
the lockfile-first discovery are unchanged, PATCH and binary reads are new.
"""

from __future__ import annotations

import base64
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# Keeps a console window from flashing up when we shell out under pythonw.
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_TOKEN_RE = re.compile(r"--remoting-auth-token=([\w-]+)")
_PORT_RE = re.compile(r"--app-port=(\d+)")
_INSTALL_RE = re.compile(r'--install-directory=([^"]+)')
_YAML_PATH_RE = re.compile(r'product_install_full_path:\s*"?([^"\r\n]+)"?')

# Written by Riot's installer; the cheapest way to learn where the game lives.
_PRODUCT_SETTINGS = Path(
    os.environ.get("ProgramData", r"C:\ProgramData")
) / "Riot Games/Metadata/league_of_legends.live/league_of_legends.live.product_settings.yaml"

_DEFAULT_INSTALL = Path(r"C:\Riot Games\League of Legends")

# No double quotes in here on purpose: subprocess wraps the whole script in
# quotes for the Windows command line, and nested ones do not survive the trip.
_PS_COMMAND = (
    "Get-CimInstance Win32_Process -Filter 'name=''LeagueClientUx.exe''' "
    "| Select-Object -First 1 -ExpandProperty CommandLine"
)


class ClientUnavailable(Exception):
    """The League client is not running, or stopped answering."""


@dataclass(frozen=True)
class Credentials:
    port: int
    token: str
    install_dir: str | None = None

    @property
    def base_url(self) -> str:
        return f"https://127.0.0.1:{self.port}"


def _install_dir_from_metadata() -> Path | None:
    try:
        match = _YAML_PATH_RE.search(_PRODUCT_SETTINGS.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return None
    return Path(match.group(1)) if match else None


def credentials_from_lockfile(install_dir: str | Path) -> Credentials:
    """Read `<install>/lockfile`, written on start and deleted on exit.

    Format: ``LeagueClient:<pid>:<port>:<password>:https``
    """
    lockfile = Path(install_dir) / "lockfile"
    try:
        parts = lockfile.read_text(encoding="utf-8").strip().split(":")
    except OSError as exc:
        raise ClientUnavailable(f"no lockfile at {lockfile}") from exc
    if len(parts) < 4 or not parts[2].isdigit():
        raise ClientUnavailable(f"malformed lockfile at {lockfile}")
    return Credentials(port=int(parts[2]), token=parts[3], install_dir=str(install_dir))


def credentials_from_process() -> Credentials:
    """Authoritative fallback: read the credentials off the client's command line."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_COMMAND],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClientUnavailable(f"could not query processes: {exc}") from exc

    command_line = proc.stdout or ""
    token = _TOKEN_RE.search(command_line)
    port = _PORT_RE.search(command_line)
    if not token or not port:
        raise ClientUnavailable("LeagueClientUx.exe is not running")

    install = _INSTALL_RE.search(command_line)
    return Credentials(
        port=int(port.group(1)),
        token=token.group(1),
        install_dir=install.group(1).strip() if install else None,
    )


def discover(known_install_dir: str | Path | None = None) -> Credentials:
    """Find a running client, cheapest strategy first.

    Reading the lockfile costs one file read; the process query costs a
    PowerShell launch, so it is the last resort. Credentials from either source
    still have to be proven by a real request -- a lockfile can be left behind
    by a client that crashed.
    """
    for candidate in (known_install_dir, _install_dir_from_metadata(), _DEFAULT_INSTALL):
        if not candidate:
            continue
        try:
            return credentials_from_lockfile(candidate)
        except ClientUnavailable:
            continue
    return credentials_from_process()


def _loopback_ssl_context() -> ssl.SSLContext:
    """The client signs its certificate with Riot's own private CA.

    Chain validation would only tell us something we already know: the traffic
    never leaves 127.0.0.1, and every request carries the per-session token the
    client just handed us.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class LcuClient:
    """Minimal JSON client for one League client session."""

    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=_loopback_ssl_context())
        )
        secret = base64.b64encode(f"riot:{credentials.token}".encode()).decode()
        self._headers = {"Authorization": f"Basic {secret}", "Accept": "application/json"}

    # -- plumbing --------------------------------------------------------

    def request(self, method: str, path: str, payload=None, timeout: float = 4.0):
        """Return ``(status, parsed_body)``. HTTP errors are values, not exceptions.

        A 404 is a normal answer here: the ready-check and champ-select
        endpoints simply do not exist while nothing is going on.
        """
        status, raw = self.raw_request(method, path, payload, timeout)
        return status, _decode(raw)

    def raw_request(self, method: str, path: str, payload=None, timeout: float = 4.0):
        """Same, but hands back undecoded bytes -- used for champion portraits."""
        headers = dict(self._headers)
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif method in ("POST", "PATCH", "PUT"):
            body = b""

        request = urllib.request.Request(
            self.credentials.base_url + path, method=method, headers=headers, data=body
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except (urllib.error.URLError, ssl.SSLError, OSError) as exc:
            raise ClientUnavailable(str(exc)) from exc

    def get(self, path: str, timeout: float = 4.0):
        return self.request("GET", path, timeout=timeout)

    def post(self, path: str, payload=None, timeout: float = 4.0):
        return self.request("POST", path, payload, timeout)

    def patch(self, path: str, payload=None, timeout: float = 4.0):
        return self.request("PATCH", path, payload, timeout)

    def get_bytes(self, path: str, timeout: float = 8.0) -> bytes | None:
        status, raw = self.raw_request("GET", path, timeout=timeout)
        return raw if 200 <= status < 300 else None

    # -- the one call everything else leans on ---------------------------

    def current_summoner(self) -> dict | None:
        status, body = self.get("/lol-summoner/v1/current-summoner")
        return body if status == 200 and isinstance(body, dict) else None


def _decode(raw: bytes):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def ok(status: int) -> bool:
    return 200 <= status < 300
