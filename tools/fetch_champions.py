"""Refresh assets/champions.json, the offline champion list.

The live client serves a better list, but it is only there while the client is
running -- this snapshot lets champion search work before League is even open.

    python tools/fetch_champions.py
"""

import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "champions.json"
VERSIONS = "https://ddragon.leagueoflegends.com/api/versions.json"


def fetch(url: str):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def main() -> None:
    version = fetch(VERSIONS)[0]
    payload = fetch(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json")

    champions = sorted(
        ({"id": int(entry["key"]), "name": entry["name"], "alias": entry["id"]}
         for entry in payload["data"].values()),
        key=lambda champion: champion["name"],
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"version": version, "champions": champions}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"wrote {OUT} - {len(champions)} champions from patch {version}")


if __name__ == "__main__":
    main()
