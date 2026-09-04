"""The champion list behind the search box.

Bundled snapshot first, so search works before League is even open; the running
client's own list replaces it when there is one, so a champion released after
the snapshot still shows up.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from core.paths import assets_dir

from .lcu_client import LcuClient

SUMMARY = "/lol-game-data/assets/v1/champion-summary.json"
PORTRAIT = "/lol-game-data/assets/v1/champion-icons/{champion_id}.png"

BUNDLED = assets_dir() / "champions.json"


@dataclass(frozen=True)
class Champion:
    id: int
    name: str
    alias: str
    title: str = ""

    @property
    def search_key(self) -> str:
        return f"{_fold(self.name)} {_fold(self.alias)}"


def _fold(text: str) -> str:
    """Lowercase, strip accents and punctuation, so `khazix` finds Kha'Zix."""
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in stripped if not unicodedata.combining(char))
    return "".join(char for char in stripped.lower() if char.isalnum())


class Catalog:
    """Champion lookups. Cheap to build, safe to rebuild at any time."""

    def __init__(self, champions: list[Champion] | None = None) -> None:
        self._champions: list[Champion] = []
        self._by_id: dict[int, Champion] = {}
        self.source = "empty"
        self.version = ""       # the patch the bundled list came from
        if champions is not None:
            self._replace(champions, "given")

    # -- loading ---------------------------------------------------------

    @classmethod
    def bundled(cls) -> "Catalog":
        catalog = cls()
        try:
            payload = json.loads(BUNDLED.read_text(encoding="utf-8-sig"))
            entries = payload.get("champions") if isinstance(payload, dict) else payload
            if isinstance(payload, dict):
                catalog.version = str(payload.get("version") or "")
            catalog._replace(_parse(entries), f"bundled ({catalog.version or '?'})")
        except (OSError, ValueError, AttributeError, TypeError):
            pass  # an empty catalog is survivable; the client may still fill it
        return catalog

    def refresh_from_client(self, client: LcuClient) -> bool:
        """Replace the list with the running client's own. False if it would not say."""
        try:
            status, body = client.get(SUMMARY, timeout=8.0)
        except Exception:  # the caller decides what a dead client means
            return False
        if status != 200 or not isinstance(body, list):
            return False
        champions = _parse(body)
        if not champions:
            return False
        champions = [
            champion if champion.title else
            Champion(champion.id, champion.name, champion.alias, self.title_of(champion.id))
            for champion in champions
        ]
        self._replace(champions, "league client")
        return True

    def _replace(self, champions: list[Champion], source: str) -> None:
        self._champions = sorted(champions, key=lambda champion: champion.name)
        self._by_id = {champion.id: champion for champion in self._champions}
        self.source = source

    # -- lookups ---------------------------------------------------------

    def __len__(self) -> int:
        return len(self._champions)

    @property
    def all(self) -> list[Champion]:
        return list(self._champions)

    def by_id(self, champion_id: int) -> Champion | None:
        return self._by_id.get(int(champion_id))

    def name_of(self, champion_id: int) -> str:
        champion = self.by_id(champion_id)
        return champion.name if champion else ""

    def title_of(self, champion_id: int) -> str:
        champion = self.by_id(champion_id)
        return champion.title if champion else ""

    def alias_of(self, champion_id: int) -> str:
        champion = self.by_id(champion_id)
        return champion.alias if champion else ""

    def search(self, query: str, limit: int = 8) -> list[Champion]:
        """Name matches, best first: exact, then prefix, then anywhere."""
        needle = _fold(query)
        if not needle:
            return []

        exact: list[Champion] = []
        prefix: list[Champion] = []
        anywhere: list[Champion] = []
        for champion in self._champions:
            name, alias = _fold(champion.name), _fold(champion.alias)
            if needle in (name, alias):
                exact.append(champion)
            elif name.startswith(needle) or alias.startswith(needle):
                prefix.append(champion)
            elif needle in champion.search_key:
                anywhere.append(champion)
        return (exact + prefix + anywhere)[:limit]


def _parse(entries) -> list[Champion]:
    champions = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        try:
            champion_id = int(entry.get("id", 0))
        except (TypeError, ValueError):
            continue
        name = str(entry.get("name") or "").strip()
        # The client's list carries a id=-1 "None" placeholder; drop it.
        if champion_id <= 0 or not name:
            continue
        champions.append(
            Champion(
                champion_id,
                name,
                str(entry.get("alias") or name),
                str(entry.get("title") or ""),
            )
        )
    return champions


def portrait_path(champion_id: int) -> str:
    return PORTRAIT.format(champion_id=int(champion_id))
