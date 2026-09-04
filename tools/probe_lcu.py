"""Check every endpoint the app uses against the running League client.

Read-only: it never accepts a queue, hovers, locks in or sends a message. Run it
with the client open to confirm the routes still answer the way the app expects.

    python tools/probe_lcu.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from league import champion_select as cs, chat, champions, gameflow, matchmaking as mm  # noqa: E402
from league.lcu_client import ClientUnavailable, LcuClient, discover  # noqa: E402

READS = [
    ("gameflow phase", gameflow.ENDPOINT),
    ("ready check", mm.READY_CHECK),
    ("champ select session", cs.SESSION),
    ("pickable champions", cs.PICKABLE),
    ("champion list", champions.SUMMARY),
    ("chat conversations", chat.CONVERSATIONS),
    ("current summoner", "/lol-summoner/v1/current-summoner"),
]


def summarise(path: str, body) -> str:
    """A short, non-sensitive description of what came back."""
    if body is None:
        return "-"
    if isinstance(body, str):
        return body
    if isinstance(body, list):
        if path == chat.CONVERSATIONS:
            # Types only; conversation contents are none of our business.
            types = sorted({str(entry.get("type")) for entry in body if isinstance(entry, dict)})
            return f"{len(body)} conversations: {', '.join(types)}"
        return f"{len(body)} entries"
    if isinstance(body, dict):
        if path == mm.READY_CHECK:
            pop = mm.ReadyCheck.parse(body)
            return f"state={pop.state} response={pop.player_response} timer={pop.timer}"
        if path == cs.SESSION:
            session = cs.Session.parse(body)
            return (
                f"cell={session.local_cell_id} phase={session.phase} "
                f"actions={len(session.actions)} my_turn={session.is_my_pick_turn} "
                f"time_left={session.time_left:.0f}s taken={len(session.taken_champion_ids)}"
            )
        if path.endswith("current-summoner"):
            return f"gameName present: {bool(body.get('gameName') or body.get('displayName'))}"
        if "message" in body:
            return str(body.get("message"))
        return ", ".join(sorted(body)[:8])
    return type(body).__name__


def main() -> int:
    try:
        credentials = discover()
    except ClientUnavailable as exc:
        print(f"League client not found: {exc}")
        return 1

    client = LcuClient(credentials)
    print(f"connected on port {credentials.port}\n")
    print(f"{'endpoint':<24} {'status':>6}  detail")
    print("-" * 78)

    results = {}
    for name, path in READS:
        try:
            status, body = client.get(path)
        except ClientUnavailable as exc:
            print(f"{name:<24} {'---':>6}  {exc}")
            return 1
        results[path] = status
        print(f"{name:<24} {status:>6}  {summarise(path, body)}")

    print("\nwrite endpoints (not called by this probe):")
    print(f"  POST  {mm.ACCEPT}")
    print(f"  PATCH {cs.ACTION.format(action_id='<id>')}   {{championId}} / {{championId, completed}}")
    print(f"  POST  {chat.MESSAGES.format(conversation_id='<id>')}   {{body, type:chat}}")

    catalog = champions.Catalog.bundled()
    if catalog.refresh_from_client(client):
        print(f"\nchampion catalog from client: {len(catalog)} champions")
    else:
        print(f"\nchampion catalog fell back to the bundle: {len(catalog)} champions")

    expected_when_idle = {gameflow.ENDPOINT: 200, champions.SUMMARY: 200}
    bad = [path for path, want in expected_when_idle.items() if results.get(path) != want]
    if bad:
        print(f"\nUNEXPECTED: these should answer 200 at any time -> {bad}")
        return 1
    print("\nAll endpoints behaved as the app expects.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
