"""Reading the gameflow phase."""

import unittest

from league import gameflow
from tests.mocks import FakeLcu


class GameflowTest(unittest.TestCase):
    def test_reads_the_phase(self):
        client = FakeLcu({gameflow.ENDPOINT: (200, "ChampSelect")})

        self.assertEqual(gameflow.read(client), "ChampSelect")

    def test_missing_endpoint_reads_as_unknown(self):
        self.assertEqual(gameflow.read(FakeLcu()), "Unknown")

    def test_nonsense_body_reads_as_unknown(self):
        client = FakeLcu({gameflow.ENDPOINT: (200, {"unexpected": True})})

        self.assertEqual(gameflow.read(client), "Unknown")

    def test_known_phases_have_readable_labels(self):
        self.assertEqual(gameflow.label("Matchmaking"), "In queue")
        self.assertEqual(gameflow.label("ChampSelect"), "Champion select")

    def test_unknown_phase_is_passed_through(self):
        # A phase Riot adds later should surface, not vanish.
        self.assertEqual(gameflow.label("SomeNewPhase"), "SomeNewPhase")

    def test_queue_phases_are_the_ones_that_can_pop(self):
        self.assertIn("Matchmaking", gameflow.QUEUE_PHASES)
        self.assertIn("ReadyCheck", gameflow.QUEUE_PHASES)
        self.assertNotIn("ChampSelect", gameflow.QUEUE_PHASES)


if __name__ == "__main__":
    unittest.main()
