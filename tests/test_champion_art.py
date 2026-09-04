"""Champion icons and splash art: where they come from, and the cache."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from league import champion_art
from tests.mocks import FakeLcu

NEEKO = 518
SPLASH_PATH = "/lol-game-data/assets/ASSETS/Characters/Neeko/Skins/Base/Images/n_splash_0.jpg"


def client_with_art() -> FakeLcu:
    return FakeLcu(
        {
            champion_art.LCU_ICON.format(champion_id=NEEKO): (200, b"icon-bytes"),
            champion_art.LCU_DETAIL.format(champion_id=NEEKO): (
                200,
                {"skins": [{"splashPath": SPLASH_PATH, "tilePath": "/tile.jpg"}]},
            ),
            SPLASH_PATH: (200, b"splash-bytes"),
        }
    )


class FromClientTest(unittest.TestCase):
    def test_the_icon_has_a_fixed_address(self):
        client = client_with_art()

        data = champion_art._from_client(champion_art.ICON, NEEKO, client)

        self.assertEqual(data, b"icon-bytes")

    def test_the_splash_is_looked_up_in_the_champion_document(self):
        # The client does not serve splashes at a guessable path -- the real
        # one is named inside the champion's own JSON.
        client = client_with_art()

        data = champion_art._from_client(champion_art.SPLASH, NEEKO, client)

        self.assertEqual(data, b"splash-bytes")
        self.assertIn(champion_art.LCU_DETAIL.format(champion_id=NEEKO), client.paths("GET"))
        self.assertIn(SPLASH_PATH, client.paths("GET"))

    def test_an_uncentered_splash_is_accepted_when_there_is_no_centred_one(self):
        client = FakeLcu(
            {
                champion_art.LCU_DETAIL.format(champion_id=NEEKO): (
                    200,
                    {"skins": [{"uncenteredSplashPath": SPLASH_PATH}]},
                ),
                SPLASH_PATH: (200, b"splash-bytes"),
            }
        )

        self.assertEqual(
            champion_art._from_client(champion_art.SPLASH, NEEKO, client), b"splash-bytes"
        )

    def test_a_champion_document_without_skins_gives_nothing(self):
        client = FakeLcu(
            {champion_art.LCU_DETAIL.format(champion_id=NEEKO): (200, {"skins": []})}
        )

        self.assertIsNone(champion_art._from_client(champion_art.SPLASH, NEEKO, client))

    def test_no_client_means_no_bytes(self):
        self.assertIsNone(champion_art._from_client(champion_art.ICON, NEEKO, None))

    def test_a_client_that_throws_does_not_take_the_app_down(self):
        client = client_with_art()
        client.unavailable = True

        self.assertIsNone(champion_art._from_client(champion_art.ICON, NEEKO, client))


class CacheTest(unittest.TestCase):
    def setUp(self):
        self._temp = TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        patcher = mock.patch.object(champion_art, "CACHE_DIR", Path(self._temp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_bytes_survive_a_round_trip(self):
        champion_art.store(champion_art.ICON, NEEKO, b"icon-bytes")

        self.assertEqual(champion_art.cached(champion_art.ICON, NEEKO), b"icon-bytes")

    def test_nothing_cached_is_reported_as_nothing(self):
        self.assertIsNone(champion_art.cached(champion_art.ICON, NEEKO))

    def test_the_client_is_only_asked_once(self):
        client = client_with_art()

        first = champion_art.load(champion_art.ICON, NEEKO, client=client)
        calls_after_first = len(client.calls)
        second = champion_art.load(champion_art.ICON, NEEKO, client=client)

        self.assertEqual(first, b"icon-bytes")
        self.assertEqual(second, b"icon-bytes")
        self.assertEqual(len(client.calls), calls_after_first, "the cache should have answered")

    def test_an_unknown_champion_asks_for_nothing(self):
        client = client_with_art()

        self.assertIsNone(champion_art.load(champion_art.ICON, 0, client=client))
        self.assertEqual(client.calls, [])

    def test_icons_and_splashes_are_cached_separately(self):
        champion_art.store(champion_art.ICON, NEEKO, b"icon-bytes")
        champion_art.store(champion_art.SPLASH, NEEKO, b"splash-bytes")

        self.assertEqual(champion_art.cached(champion_art.ICON, NEEKO), b"icon-bytes")
        self.assertEqual(champion_art.cached(champion_art.SPLASH, NEEKO), b"splash-bytes")


if __name__ == "__main__":
    unittest.main()
