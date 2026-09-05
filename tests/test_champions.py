"""The champion list: what gets into it, and what is quietly left out.

The client's own list is not a clean roster. It opens with an `id=-1`
placeholder, and since the Jade mode every champion in it appears twice --
once as itself, once under an offset id with a prefixed alias. Both would show
up in the search box, and the second copy could never be locked in.
"""

import unittest

from league.champions import Catalog, Champion, _fold, _parse

AHRI, KATARINA = 103, 55


def entry(champion_id: int, name: str, alias: str | None = None) -> dict:
    return {"id": champion_id, "name": name, "alias": alias if alias is not None else name}


def summary_from_the_client() -> list[dict]:
    """A shortened copy of what /champion-summary.json really serves."""
    return [
        entry(-1, "None"),
        entry(AHRI, "Ahri"),
        entry(KATARINA, "Katarina"),
        entry(62, "Wukong", "MonkeyKing"),
        entry(60000 + AHRI, "Ahri", "Jade_Ahri"),
        entry(60000 + KATARINA, "Katarina", "Jade_Katarina"),
    ]


class ParseTest(unittest.TestCase):
    def test_every_champion_appears_once(self):
        champions = _parse(summary_from_the_client())

        self.assertEqual(
            sorted(champion.name for champion in champions),
            ["Ahri", "Katarina", "Wukong"],
        )

    def test_the_none_placeholder_is_dropped(self):
        self.assertNotIn(-1, [champion.id for champion in _parse(summary_from_the_client())])

    def test_a_game_modes_copy_is_left_out(self):
        by_name = {champion.name: champion for champion in _parse(summary_from_the_client())}

        self.assertEqual(by_name["Ahri"].id, AHRI, "the copy won over the real champion")
        self.assertEqual(by_name["Ahri"].alias, "Ahri")

    def test_the_lowest_id_wins_whatever_the_order(self):
        champions = _parse([entry(60000 + AHRI, "Ahri", "JadeAhri"), entry(AHRI, "Ahri")])

        self.assertEqual([champion.id for champion in champions], [AHRI])

    def test_an_alias_that_is_simply_one_word_is_kept(self):
        champions = _parse([entry(62, "Wukong", "MonkeyKing")])

        self.assertEqual(champions[0].alias, "MonkeyKing")

    def test_nonsense_entries_are_skipped_rather_than_fatal(self):
        champions = _parse([None, "Ahri", {}, {"id": "x", "name": "Ahri"}, entry(AHRI, "Ahri")])

        self.assertEqual([champion.id for champion in champions], [AHRI])


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(_parse(summary_from_the_client()))

    def test_a_search_returns_one_of_each(self):
        self.assertEqual([champion.id for champion in self.catalog.search("ahri")], [AHRI])

    def test_the_whole_roster_is_in_alphabetical_order(self):
        self.assertEqual(
            [champion.name for champion in self.catalog.all], ["Ahri", "Katarina", "Wukong"]
        )

    def test_the_bundled_list_has_no_repeats_either(self):
        bundled = Catalog.bundled()
        names = [champion.name for champion in bundled.all]

        self.assertGreater(len(names), 150, "the bundled roster looks empty")
        self.assertEqual(len(names), len(set(names)))

    def test_folding_ignores_punctuation_and_case(self):
        self.assertEqual(_fold("Kha'Zix"), "khazix")
        self.assertEqual(_fold("Nunu & Willump"), "nunuwillump")

    def test_a_champion_carries_no_title(self):
        self.assertEqual(Champion(AHRI, "Ahri", "Ahri").name, "Ahri")
        self.assertNotIn("title", Champion(AHRI, "Ahri", "Ahri").__dict__)


if __name__ == "__main__":
    unittest.main()
