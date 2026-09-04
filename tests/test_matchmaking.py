"""Detecting the queue pop and answering it."""

import unittest

from league import matchmaking as mm
from tests.mocks import FakeLcu, ready_check_payload


class ReadyCheckTest(unittest.TestCase):
    def test_detects_a_live_pop(self):
        client = FakeLcu({mm.READY_CHECK: (200, ready_check_payload())})

        pop = mm.read(client)

        self.assertIsNotNone(pop)
        self.assertTrue(pop.is_live)
        self.assertTrue(pop.is_unanswered)

    def test_no_queue_means_no_pop(self):
        # The client answers 404 with "Not attached to a matchmaking queue".
        self.assertIsNone(mm.read(FakeLcu()))

    def test_answered_pop_is_no_longer_unanswered(self):
        client = FakeLcu({mm.READY_CHECK: (200, ready_check_payload(response="Accepted"))})

        pop = mm.read(client)

        self.assertTrue(pop.is_live)
        self.assertFalse(pop.is_unanswered)

    def test_declined_pop_is_recognised(self):
        client = FakeLcu({mm.READY_CHECK: (200, ready_check_payload(response="Declined"))})

        self.assertEqual(mm.read(client).player_response, mm.DECLINED)

    def test_a_pop_that_is_not_in_progress_is_not_live(self):
        client = FakeLcu({mm.READY_CHECK: (200, ready_check_payload(state="Invalid"))})

        self.assertFalse(mm.read(client).is_live)

    def test_missing_fields_do_not_explode(self):
        client = FakeLcu({mm.READY_CHECK: (200, {})})

        pop = mm.read(client)

        self.assertFalse(pop.is_live)
        self.assertEqual(pop.player_response, mm.NO_ANSWER)


class AcceptTest(unittest.TestCase):
    def test_accept_posts_to_the_accept_endpoint(self):
        client = FakeLcu({("POST", mm.ACCEPT): (204, None)})

        self.assertTrue(mm.accept(client))
        self.assertEqual(client.paths("POST"), [mm.ACCEPT])

    def test_refused_accept_reports_failure(self):
        client = FakeLcu({("POST", mm.ACCEPT): (404, {"message": "Not attached to a queue."})})

        self.assertFalse(mm.accept(client))


if __name__ == "__main__":
    unittest.main()
