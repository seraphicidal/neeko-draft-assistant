
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

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_TOKEN_RE = re.compile(r"--remoting-auth-token=([\w-]+)")
_PORT_RE = re.compile(r"--app-port=(\d+)")
_INSTALL_RE = re.compile(r'--install-directory=([^"]+)')
_YAML_PATH_RE = re.compile(r'product_install_full_path:\s*"?([^"\r\n]+)"?')

_PRODUCT_SETTINGS = Path(
    os.environ.get("ProgramData", r"C:\ProgramData")
) / "Riot Games/Metadata/league_of_legends.live/league_of_legends.live.product_settings.yaml"

_DEFAULT_INSTALL = Path(r"C:\Riot Games\League of Legends")

_PS_COMMAND = (
    "Get-CimInstance Win32_Process -Filter 'name=''LeagueClientUx.exe''' "
    "| Select-Object -First 1 -ExpandProperty CommandLine"
)


class ClientUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Credentials:
    port: int
    token: str
    install_dir: str | None = None

    @property
    def base_url(self) -> str:
        return f"https://127.0.0.1:{self.port}"


def _is_process_running(process_name: str) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        import ctypes.wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.wintypes.DWORD),
                ("cntUsage", ctypes.wintypes.DWORD),
                ("th32ProcessID", ctypes.wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", ctypes.wintypes.DWORD),
                ("cntThreads", ctypes.wintypes.DWORD),
                ("th32ParentProcessID", ctypes.wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(2, 0)
        if snapshot in (-1, 0):
            return True
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        found = False
        name_lower = process_name.lower()
        if ctypes.windll.kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.lower() == name_lower:
                    found = True
                    break
                if not ctypes.windll.kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
        ctypes.windll.kernel32.CloseHandle(snapshot)
        return found
    except Exception:
        return True


def _install_dir_from_metadata() -> Path | None:
    try:
        match = _YAML_PATH_RE.search(_PRODUCT_SETTINGS.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return None
    return Path(match.group(1)) if match else None


def _candidate_install_dirs() -> list[Path]:
    candidates = []
    meta = _install_dir_from_metadata()
    if meta:
        candidates.append(meta)
    candidates.append(_DEFAULT_INSTALL)
    if sys.platform == "win32":
        for letter in ("D", "E", "F", "G"):
            candidate = Path(f"{letter}:/Riot Games/League of Legends")
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def credentials_from_lockfile(install_dir: str | Path) -> Credentials:
    lockfile = Path(install_dir) / "lockfile"
    try:
        parts = lockfile.read_text(encoding="utf-8").strip().split(":")
    except OSError as exc:
        raise ClientUnavailable(f"no lockfile at {lockfile}") from exc
    if len(parts) < 4 or not parts[2].isdigit():
        raise ClientUnavailable(f"malformed lockfile at {lockfile}")
    return Credentials(port=int(parts[2]), token=parts[3], install_dir=str(install_dir))


def credentials_from_process() -> Credentials:
    if sys.platform == "win32" and not _is_process_running("LeagueClientUx.exe"):
        raise ClientUnavailable("LeagueClientUx.exe is not running")

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
    candidates = [known_install_dir] if known_install_dir else []
    candidates.extend(_candidate_install_dirs())
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return credentials_from_lockfile(candidate)
        except ClientUnavailable:
            continue
    return credentials_from_process()


def _loopback_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class LcuClient:

    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=_loopback_ssl_context())
        )
        secret = base64.b64encode(f"riot:{credentials.token}".encode()).decode()
        self._headers = {"Authorization": f"Basic {secret}", "Accept": "application/json"}

    def request(self, method: str, path: str, payload=None, timeout: float = 4.0):
        status, raw = self.raw_request(method, path, payload, timeout)
        return status, _decode(raw)

    def raw_request(self, method: str, path: str, payload=None, timeout: float = 4.0):
        headers = dict(self._headers)
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif method in ("POST", "PATCH", "PUT"):
            body = b""

        norm_path = path if path.startswith("/") else f"/{path}"
        request = urllib.request.Request(
            self.credentials.base_url + norm_path, method=method, headers=headers, data=body
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
