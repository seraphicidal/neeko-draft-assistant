
from __future__ import annotations

from .lcu_client import LcuClient, ok

CONVERSATIONS = "/lol-chat/v1/conversations"
MESSAGES = "/lol-chat/v1/conversations/{conversation_id}/messages"

CHAMP_SELECT_TYPE = "championSelect"


def champ_select_conversation_id(client: LcuClient) -> str | None:
    status, body = client.get(CONVERSATIONS)
    if status != 200 or not isinstance(body, list):
        return None
    for conversation in body:
        if not isinstance(conversation, dict):
            continue
        if conversation.get("type") == CHAMP_SELECT_TYPE:
            conversation_id = str(conversation.get("id") or "")
            if conversation_id:
                return conversation_id
    return None


def send(client: LcuClient, conversation_id: str, body: str) -> bool:
    status, _ = client.post(
        MESSAGES.format(conversation_id=conversation_id),
        {"body": body, "type": "chat"},
    )
    return ok(status)
