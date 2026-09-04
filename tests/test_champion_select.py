"""Reading the draft: whose turn it is, and what is still on the table."""

import unittest

from league import champion_select as cs
from tests.mocks import FakeLcu, action, session_payload

AHRI, NEEKO, LUX, YASUO = 103, 518, 99, 157


def parse(**kwargs) -> cs.Session:
    return cs.Session.parse(session_payload(**kwargs))


class DetectionTest(unittest.TestCase):
    def test_detects_champion_select(self):
        client = FakeLcu({cs.SESSION: (200, session_payload())})

        self.assertIsNotNone(cs.read(client))

    def test_no_draft_means_no_session(self):
        self.assertIsNone(cs.read(FakeLcu()))

    def test_reads_the_timer_in_seconds(self):
        session = parse(time_left_ms=27400)

        self.assertAlmostEqual(session.time_left, 27.4, places=2)

    def test_reads_the_declared_intent(self):
        self.assertEqual(parse(pick_intent=NEEKO).pick_intent, NEEKO)


class MyTurnTest(unittest.TestCase):
    def test_my_pick_action_is_the_one_with_my_cell_id(self):
        session = parse(
            local_cell=2,
            actions=[[action(7, cell=1), action(8, cell=2), action(9, cell=3)]],
        )

        self.assertEqual(session.my_pick_action.id, 8)

    def test_it_is_my_turn_when_my_action_is_in_progress(self):
        session = parse(local_cell=2, actions=[[action(8, cell=2, in_progress=True)]])

        self.assertTrue(session.is_my_pick_turn)

    def test_it_is_not_my_turn_while_someone_else_picks(self):
        session = parse(
            local_cell=2,
            actions=[[action(7, cell=1, in_progress=True), action(8, cell=2)]],
        )

        self.assertFalse(session.is_my_pick_turn)

    def test_a_ban_turn_is_not_a_pick_turn(self):
        session = parse(
            local_cell=2,
            actions=[[action(3, cell=2, kind="ban", in_progress=True)]],
        )

        self.assertTrue(session.is_my_ban_turn)
        self.assertFalse(session.is_my_pick_turn)

    def test_completed_pick_is_reported_as_locked(self):
        session = parse(
            local_cell=2,
            actions=[[action(8, cell=2, champion=NEEKO, completed=True)]],
        )

        self.assertTrue(session.has_locked)
        self.assertFalse(session.is_my_pick_turn)

    def test_spectator_style_session_has_no_pick_action(self):
        session = parse(local_cell=9, actions=[[action(1, cell=0), action(2, cell=1)]])

        self.assertIsNone(session.my_pick_action)
        self.assertFalse(session.is_my_pick_turn)


class AvailabilityTest(unittest.TestCase):
    def test_completed_bans_are_taken(self):
        session = parse(
            actions=[[action(1, cell=5, kind="ban", champion=AHRI, completed=True)]]
        )

        self.assertIn(AHRI, session.taken_champion_ids)

    def test_locked_picks_by_others_are_taken(self):
        session = parse(
            local_cell=0,
            actions=[[action(4, cell=3, champion=LUX, completed=True)]],
        )

        self.assertIn(LUX, session.taken_champion_ids)

    def test_pending_bans_and_hovers_are_not_taken_yet(self):
        session = parse(
            local_cell=0,
            actions=[
                [action(1, cell=5, kind="ban", champion=YASUO, completed=False)],
                [action(4, cell=3, champion=LUX, completed=False)],
            ],
        )

        self.assertEqual(session.taken_champion_ids, frozenset())

    def test_my_own_locked_pick_does_not_count_against_me(self):
        session = parse(
            local_cell=2,
            actions=[[action(8, cell=2, champion=NEEKO, completed=True)]],
        )

        self.assertNotIn(NEEKO, session.taken_champion_ids)

    def test_pickable_ids_are_read_as_a_set(self):
        client = FakeLcu({cs.PICKABLE: (200, [AHRI, NEEKO])})

        self.assertEqual(cs.pickable_ids(client), frozenset({AHRI, NEEKO}))

    def test_unavailable_pickable_endpoint_is_unknown_not_empty(self):
        # None must not be read as "nothing is available".
        self.assertIsNone(cs.pickable_ids(FakeLcu()))


class IdentityTest(unittest.TestCase):
    def test_the_chat_room_names_the_draft(self):
        self.assertEqual(parse(chat_id="room-42").identity, "room-42")

    def test_a_draft_without_a_chat_room_still_gets_a_stable_name(self):
        payload = session_payload(local_cell=1, actions=[[action(3, cell=1)]], chat_id="")
        first = cs.Session.parse(payload)
        second = cs.Session.parse(payload)

        self.assertTrue(first.identity)
        self.assertEqual(first.identity, second.identity)

    def test_different_drafts_get_different_names(self):
        self.assertNotEqual(parse(chat_id="room-1").identity, parse(chat_id="room-2").identity)


class WritesTest(unittest.TestCase):
    def test_declare_hovers_without_completing(self):
        client = FakeLcu({("PATCH", cs.ACTION.format(action_id=8)): (204, None)})

        self.assertTrue(cs.declare(client, 8, NEEKO))
        self.assertEqual(client.payloads("PATCH", "/actions/8"), [{"championId": NEEKO}])

    def test_lock_completes_the_action(self):
        client = FakeLcu({("PATCH", cs.ACTION.format(action_id=8)): (204, None)})

        self.assertTrue(cs.lock(client, 8, NEEKO))
        self.assertEqual(
            client.payloads("PATCH", "/actions/8"),
            [{"championId": NEEKO, "completed": True}],
        )

    def test_a_rejected_write_reports_failure(self):
        client = FakeLcu({("PATCH", cs.ACTION.format(action_id=8)): (500, {"message": "nope"})})

        self.assertFalse(cs.declare(client, 8, NEEKO))
        self.assertFalse(cs.lock(client, 8, NEEKO))


if __name__ == "__main__":
    unittest.main()
