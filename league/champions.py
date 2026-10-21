
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

    @property
    def search_key(self) -> str:
        return f"{_fold(self.name)} {_fold(self.alias)}"


def _fold(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in stripped if not unicodedata.combining(char))
    return "".join(char for char in stripped.lower() if char.isalnum())


class Catalog:

    def __init__(self, champions: list[Champion] | None = None) -> None:
        self._champions: list[Champion] = []
        self._by_id: dict[int, Champion] = {}
        self.source = "empty"
        self.version = ""
        if champions is not None:
            self._replace(champions, "given")

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
            pass
        return catalog

    def refresh_from_client(self, client: LcuClient) -> bool:
        try:
            status, body = client.get(SUMMARY, timeout=8.0)
        except Exception:
            return False
        if status != 200 or not isinstance(body, list):
            return False
        champions = _parse(body)
        if not champions:
            return False
        self._replace(champions, "league client")
        return True

    def _replace(self, champions: list[Champion], source: str) -> None:
        self._champions = sorted(champions, key=lambda champion: champion.name)
        self._by_id = {champion.id: champion for champion in self._champions}
        self.source = source

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

    def alias_of(self, champion_id: int) -> str:
        champion = self.by_id(champion_id)
        return champion.alias if champion else ""

    def search(self, query: str, limit: int = 8) -> list[Champion]:
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
    best: dict[str, Champion] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        try:
            champion_id = int(entry.get("id", 0))
        except (TypeError, ValueError):
            continue
        name = str(entry.get("name") or "").strip()
        if champion_id <= 0 or not name:
            continue
        alias = str(entry.get("alias") or name).strip()
        if "_" in alias:
            continue
        key = _fold(name)
        kept = best.get(key)
        if kept is None or champion_id < kept.id:
            best[key] = Champion(champion_id, name, alias or name)
    return list(best.values())


def portrait_path(champion_id: int) -> str:
    return PORTRAIT.format(champion_id=int(champion_id))
