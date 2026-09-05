"""The loop that does the talking: connecting, reconnecting, carrying out intents."""

import unittest

from league import champion_select as cs
from league import chat, gameflow, matchmaking as mm
from league.champions import Catalog, Champion
from league.lcu_client import ClientUnavailable
from core.logbook import LogBook
from core.settings import Settings
from core.watcher import INTERVAL_DISCONNECTED, INTERVAL_DRAFT, INTERVAL_QUEUE, Watcher
from tests.mocks import FakeLcu, action, conversations_payload, ready_check_payload, session_payload

NEEKO, AHRI = 518, 103
SUMMONER = "/lol-summoner/v1/current-summoner"


def step(watcher: Watcher) -> float:
    """One iteration of the loop, with the same error handling `run` uses."""
    try:
        return watcher._tick()
    except ClientUnavailable:
        return watcher._drop_client()


class WatcherTestCase(unittest.TestCase):
    def build(self, client, **overrides):
        settings = Settings(**overrides)
        catalog = Catalog([Champion(NEEKO, "Neeko", "Neeko"), Champion(AHRI, "Ahri", "Ahri")])
        self.events: list[tuple[str, dict]] = []
        watcher = Watcher(
            settings,
            catalog,
            LogBook(),
            lambda kind, payload: self.events.append((kind, payload)),
            connect=lambda: client,
        )
        return watcher, settings

    def kinds(self):
        return [kind for kind, _ in self.events]

    def statuses(self):
        return [payload["status"] for kind, payload in self.events if kind == "status"]


class ConnectionTest(WatcherTestCase):
    def test_connects_and_reports_the_phase(self):
        client = FakeLcu(
            {
                gameflow.ENDPOINT: (200, "Lobby"),
                SUMMONER: (200, {"gameName": "Chobot"}),
            }
        )
        watcher, _ = self.build(client)

        step(watcher)  # connect
        step(watcher)  # first real poll

        status = self.statuses()[-1]
        self.assertTrue(status.connected)
        self.assertEqual(status.phase, "Lobby")
        self.assertEqual(status.summoner, "Chobot")

    def test_no_client_backs_off_and_reports_disconnected(self):
        def refuse():
            raise ClientUnavailable("not running")

        watcher, _ = self.build(FakeLcu())
        watcher._connect_client = refuse

        interval = step(watcher)

        self.assertEqual(interval, INTERVAL_DISCONNECTED)
        self.assertFalse(self.statuses()[-1].connected)

    def test_a_client_restart_is_survived(self):
        client = FakeLcu({gameflow.ENDPOINT: (200, "None"), SUMMONER: (200, {"gameName": "x"})})
        watcher, _ = self.build(client)
        step(watcher)
        step(watcher)
        self.assertTrue(self.statuses()[-1].connected)

        client.unavailable = True          # League closes
        interval = step(watcher)
        self.assertEqual(interval, INTERVAL_DISCONNECTED)
        self.assertFalse(self.statuses()[-1].connected)

        client.unavailable = False         # and comes back
        step(watcher)
        step(watcher)

        self.assertTrue(self.statuses()[-1].connected)

    def test_the_champion_list_is_taken_from_the_client(self):
        client = FakeLcu(
            {
                gameflow.ENDPOINT: (200, "None"),
                "/lol-game-data/assets/v1/champion-summary.json": (
                    200,
                    [{"id": -1, "name": "None", "alias": "NONE"},
                     {"id": NEEKO, "name": "Neeko", "alias": "Neeko"}],
                ),
            }
        )
        watcher, _ = self.build(client)

        step(watcher)

        self.assertEqual(len(watcher.catalog), 1)  # the id=-1 placeholder is dropped
        self.assertEqual(watcher.catalog.source, "league client")


class QueueTest(WatcherTestCase):
    def test_accepts_the_pop_and_counts_it(self):
        client = FakeLcu(
            {
                gameflow.ENDPOINT: (200, "ReadyCheck"),
                mm.READY_CHECK: (200, ready_check_payload()),
                ("POST", mm.ACCEPT): (204, None),
            }
        )
        watcher, settings = self.build(client)
        step(watcher)

        interval = step(watcher)

        self.assertEqual(client.count("POST", mm.ACCEPT), 1)
        self.assertEqual(settings.accepted_total, 1)
        self.assertIn("counters", self.kinds())
        self.assertEqual(interval, INTERVAL_QUEUE)

    def test_only_the_accept_asks_for_a_desktop_notification(self):
        client = FakeLcu(
            {
                gameflow.ENDPOINT: (200, "ReadyCheck"),
                mm.READY_CHECK: (200, ready_check_payload()),
                ("POST", mm.ACCEPT): (204, None),
            }
        )
        watcher, _ = self.build(client)
        step(watcher)

        step(watcher)

        actions = [payload for kind, payload in self.events if kind == "action"]
        self.assertTrue(actions[0]["notify"], "you are away from the screen for this one")

    def test_a_refused_accept_is_retried_but_not_forever(self):
        client = FakeLcu(
            {
                gameflow.ENDPOINT: (200, "ReadyCheck"),
                mm.READY_CHECK: (200, ready_check_payload()),
                ("POST", mm.ACCEPT): (500, {"message": "no"}),
            }
        )
        watcher, settings = self.build(client)
        step(watcher)

        for _ in range(12):
            step(watcher)

        self.assertLessEqual(client.count("POST", mm.ACCEPT), 3)
        self.assertEqual(settings.accepted_total, 0)


class DraftTest(WatcherTestCase):
    def draft_client(self, actions, **session_kwargs):
        return FakeLcu(
            {
                gameflow.ENDPOINT: (200, "ChampSelect"),
                cs.SESSION: (200, session_payload(local_cell=2, actions=actions, **session_kwargs)),
                cs.PICKABLE: (200, [NEEKO, AHRI]),
                ("PATCH", cs.ACTION.format(action_id=5)): (204, None),
                chat.CONVERSATIONS: (200, conversations_payload("draft@sec")),
                ("POST", chat.MESSAGES.format(conversation_id="draft@sec")): (200, {"id": "1"}),
            }
        )

    def test_declares_the_preferred_champion(self):
        client = self.draft_client([[action(5, cell=2)]])
        watcher, _ = self.build(client, preferred_champion_id=NEEKO, auto_pick=False)
        step(watcher)

        interval = step(watcher)

        self.assertEqual(client.payloads("PATCH", "/actions/5"), [{"championId": NEEKO}])
        self.assertEqual(interval, INTERVAL_DRAFT)

    def test_locks_in_on_our_turn_and_counts_it(self):
        client = self.draft_client([[action(5, cell=2, in_progress=True)]])
        watcher, settings = self.build(
            client, preferred_champion_id=NEEKO, auto_pick=True, auto_declare=False
        )
        step(watcher)

        step(watcher)

        self.assertEqual(
            client.payloads("PATCH", "/actions/5"), [{"championId": NEEKO, "completed": True}]
        )
        self.assertEqual(settings.picks_total, 1)

    def test_repeated_polls_do_not_repeat_the_pick(self):
        client = self.draft_client([[action(5, cell=2, in_progress=True)]])
        watcher, _ = self.build(
            client, preferred_champion_id=NEEKO, auto_pick=True, auto_declare=False
        )
        step(watcher)

        for _ in range(6):
            step(watcher)

        self.assertEqual(client.count("PATCH", "/actions/5"), 1)

    def test_draft_actions_stay_out_of_the_notification_area(self):
        # Hovering, locking and chatting all happen while champion select is on
        # screen; a Windows toast on top of it would only be in the way.
        client = self.draft_client([[action(5, cell=2, in_progress=True)]])
        watcher, _ = self.build(
            client,
            preferred_champion_id=NEEKO,
            auto_pick=True,
            chat_enabled=True,
            chat_message="hello gl hf",
        )
        step(watcher)

        for _ in range(4):
            step(watcher)

        actions = [payload for kind, payload in self.events if kind == "action"]
        self.assertTrue(actions, "the draft should have produced some actions")
        for payload in actions:
            with self.subTest(action=payload["text"]):
                self.assertFalse(payload.get("notify"))

    def test_sends_the_draft_message_once(self):
        client = self.draft_client([[action(5, cell=2)]])
        watcher, _ = self.build(
            client,
            chat_enabled=True,
            chat_message="hello gl hf",
            auto_declare=False,
            auto_pick=False,
        )
        step(watcher)

        for _ in range(5):
            step(watcher)

        self.assertEqual(client.count("POST", "/messages"), 1)
        self.assertTrue(self.statuses()[-1].chat_sent)

    def test_an_unavailable_champion_produces_a_problem_not_a_pick(self):
        client = self.draft_client(
            [[action(1, cell=7, kind="ban", champion=NEEKO, completed=True),
              action(5, cell=2, in_progress=True)]]
        )
        watcher, _ = self.build(client, preferred_champion_id=NEEKO, auto_pick=True)
        step(watcher)

        step(watcher)

        self.assertEqual(client.count("PATCH", "/actions/5"), 0)
        self.assertTrue(self.statuses()[-1].problem)


if __name__ == "__main__":
    unittest.main()
