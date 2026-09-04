"""Champion icons and splash art, fetched once and kept on disk.

The running client serves both without touching the internet, so it is asked
first; Riot's public CDN is the fallback so the app still looks right before
League is even open. Either way the bytes land in a cache directory and are
never fetched twice.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path

ICON = "icon"
SPLASH = "splash"

_EXTENSIONS = {ICON: "png", SPLASH: "jpg"}

CACHE_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache"))
    / "NeekoDraftAssistant"
    / "champions"
)

# Local client asset routes. The icon has a stable address; the splash does
# not -- its real path is spelled out in the champion's own detail document,
# so it has to be looked up first.
LCU_ICON = "/lol-game-data/assets/v1/champion-icons/{champion_id}.png"
LCU_DETAIL = "/lol-game-data/assets/v1/champions/{champion_id}.json"

# Riot's public CDN, used when the client is not running.
CDN_ICON = "https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{alias}.png"
CDN_SPLASH = "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{alias}_0.jpg"

TIMEOUT = 12.0
MAX_BYTES = 4 * 1024 * 1024


def cache_path(kind: str, champion_id: int) -> Path:
    return CACHE_DIR / f"{int(champion_id)}_{kind}.{_EXTENSIONS.get(kind, 'bin')}"


def cached(kind: str, champion_id: int) -> bytes | None:
    path = cache_path(kind, champion_id)
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return data or None


def store(kind: str, champion_id: int, data: bytes) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = cache_path(kind, champion_id)
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(data)
        os.replace(temporary, path)
    except OSError:
        pass  # a cache we cannot write is still a working app, just slower


def _splash_path(champion_id: int, client) -> str | None:
    """Ask the client where this champion's default splash actually lives."""
    status, body = client.get(LCU_DETAIL.format(champion_id=champion_id))
    if status != 200 or not isinstance(body, dict):
        return None
    for skin in body.get("skins") or []:
        if not isinstance(skin, dict):
            continue
        path = skin.get("splashPath") or skin.get("uncenteredSplashPath")
        if path:
            return str(path)
    return None


def _from_client(kind: str, champion_id: int, client) -> bytes | None:
    if client is None:
        return None
    try:
        if kind == ICON:
            return client.get_bytes(LCU_ICON.format(champion_id=champion_id))
        path = _splash_path(champion_id, client)
        return client.get_bytes(path) if path else None
    except Exception:  # a dead client just means we try the CDN
        return None


def _from_cdn(kind: str, alias: str, version: str) -> bytes | None:
    if not alias:
        return None
    url = (
        CDN_ICON.format(version=version or "latest", alias=alias)
        if kind == ICON
        else CDN_SPLASH.format(alias=alias)
    )
    request = urllib.request.Request(url, headers={"User-Agent": "NeekoDraftAssistant"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read(MAX_BYTES) or None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def load(kind: str, champion_id: int, alias: str = "", version: str = "", client=None) -> bytes | None:
    """Cached bytes if we have them, otherwise client, otherwise CDN."""
    champion_id = int(champion_id or 0)
    if champion_id <= 0:
        return None

    data = cached(kind, champion_id)
    if data:
        return data

    data = _from_client(kind, champion_id, client) or _from_cdn(kind, alias, version)
    if data:
        store(kind, champion_id, data)
    return data
