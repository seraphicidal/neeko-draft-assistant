"""Finding the draft chat room and posting one line into it."""

import unittest

from league import chat
from tests.mocks import FakeLcu, conversations_payload


class ConversationTest(unittest.TestCase):
    def test_finds_the_champion_select_room(self):
        client = FakeLcu({chat.CONVERSATIONS: (200, conversations_payload("draft@sec.pvp.net"))})

        self.assertEqual(chat.champ_select_conversation_id(client), "draft@sec.pvp.net")

    def test_no_room_yet_is_not_an_error(self):
        # The room appears a moment after the draft starts.
        client = FakeLcu({chat.CONVERSATIONS: (200, [{"id": "club@x", "type": "club"}])})

        self.assertIsNone(chat.champ_select_conversation_id(client))

    def test_missing_endpoint_is_handled(self):
        self.assertIsNone(chat.champ_select_conversation_id(FakeLcu()))

    def test_junk_entries_are_skipped(self):
        client = FakeLcu({chat.CONVERSATIONS: (200, ["nonsense", {"type": "championSelect"}])})

        self.assertIsNone(chat.champ_select_conversation_id(client))


class SendTest(unittest.TestCase):
    def test_posts_the_message_body(self):
        path = chat.MESSAGES.format(conversation_id="draft@x")
        client = FakeLcu({("POST", path): (200, {"id": "1"})})

        self.assertTrue(chat.send(client, "draft@x", "hello gl hf"))
        self.assertEqual(
            client.payloads("POST", "/messages"),
            [{"body": "hello gl hf", "type": "chat"}],
        )

    def test_failure_is_reported(self):
        client = FakeLcu()

        self.assertFalse(chat.send(client, "draft@x", "hello gl hf"))


if __name__ == "__main__":
    unittest.main()
