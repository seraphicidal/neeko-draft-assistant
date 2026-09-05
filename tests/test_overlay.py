"""The champion search overlay.

Its rows are thrown away and rebuilt on every keystroke, while the art loader
fetches each champion only once. That combination is what made icons vanish
from the list the second time a champion was searched for, so the cache lookup
is pinned down here.

The list holds the whole roster now and is scrolled through, which is the
other half of it: the icons have to follow the scroll position rather than
being asked for a hundred and seventy at a time.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from league.champions import Catalog, Champion  # noqa: E402

try:
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication

    from ui.widgets import SearchOverlay

    QT_AVAILABLE = True
except Exception:  # pragma: no cover - only when PySide6 is missing
    QT_AVAILABLE = False

NEEKO, AHRI, LUX = 518, 103, 99


@unittest.skipUnless(QT_AVAILABLE, "PySide6 is not installed")
class SearchOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.catalog = Catalog(
            [
                Champion(NEEKO, "Neeko", "Neeko"),
                Champion(AHRI, "Ahri", "Ahri"),
                Champion(LUX, "Lux", "Lux"),
            ]
        )
        self.overlay = SearchOverlay(self.catalog)
        self.requested: list[int] = []
        self.overlay.art_wanted.connect(lambda _kind, champion_id: self.requested.append(champion_id))

    def a_pixmap(self) -> QPixmap:
        pixmap = QPixmap(32, 32)
        pixmap.fill()
        return pixmap

    def test_searching_lists_the_matches(self):
        self.overlay._on_typed("nee")

        self.assertEqual(self.overlay.results.count(), 1)
        self.assertIn(NEEKO, self.overlay._rows)

    def test_an_icon_we_already_have_is_shown_without_asking_again(self):
        cache = {NEEKO: self.a_pixmap()}
        self.overlay.pixmap_for = cache.get

        self.overlay._on_typed("nee")

        self.assertNotIn(NEEKO, self.requested, "the loader was asked for a cached icon")
        row = self.overlay._rows[NEEKO]
        self.assertIsNotNone(row.icon._pixmap)

    def test_an_icon_we_do_not_have_is_requested(self):
        self.overlay._on_typed("ahri")

        self.assertEqual(self.requested, [AHRI])

    def test_the_icon_survives_a_second_search(self):
        # The regression: the loader answers a champion once, so a row built
        # for a later search has to come from the cache instead.
        cache: dict[int, QPixmap] = {}
        self.overlay.pixmap_for = cache.get

        self.overlay._on_typed("nee")
        self.assertEqual(self.requested, [NEEKO])
        cache[NEEKO] = self.a_pixmap()          # the loader answered
        self.overlay.set_pixmap(NEEKO, cache[NEEKO])

        self.overlay._on_typed("lux")           # rows are rebuilt
        self.overlay._on_typed("nee")           # and back again

        self.assertEqual(self.requested.count(NEEKO), 1, "asked for the same icon twice")
        self.assertIsNotNone(self.overlay._rows[NEEKO].icon._pixmap)

    def test_late_art_reaches_the_row_that_is_showing(self):
        self.overlay._on_typed("ahri")

        self.overlay.set_pixmap(AHRI, self.a_pixmap())

        self.assertIsNotNone(self.overlay._rows[AHRI].icon._pixmap)

    def test_art_for_a_champion_no_longer_listed_is_ignored(self):
        self.overlay._on_typed("ahri")

        self.overlay.set_pixmap(LUX, self.a_pixmap())  # must not raise

        self.assertNotIn(LUX, self.overlay._rows)

    def test_a_search_with_no_matches_says_so(self):
        self.overlay._on_typed("zzzz")

        self.assertEqual(self.overlay.results.count(), 0)
        self.assertIn("No champion", self.overlay.hint.text())

    def test_the_same_search_twice_keeps_the_rows_it_had(self):
        # Rebuilding identical rows would throw away icons that had arrived.
        self.overlay._on_typed("nee")
        row = self.overlay._rows[NEEKO]
        self.overlay.set_pixmap(NEEKO, self.a_pixmap())

        self.overlay._on_typed("neek")

        self.assertIs(self.overlay._rows[NEEKO], row)
        self.assertTrue(row.has_pixmap())

    def test_champions_carry_no_title(self):
        # Titles like "the Sinister Blade" were taken out of the interface, and
        # out of the model with it so nothing keeps fetching them.
        from dataclasses import fields

        self.assertNotIn("title", [entry.name for entry in fields(Champion)])


@unittest.skipUnless(QT_AVAILABLE, "PySide6 is not installed")
class ScrollingTest(unittest.TestCase):
    """The whole roster is listed; only what is in view is fetched."""

    ROSTER = 60

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.catalog = Catalog(
            [Champion(100 + index, f"Champion {index:02d}", f"C{index:02d}")
             for index in range(self.ROSTER)]
        )
        self.overlay = SearchOverlay(self.catalog)
        self.overlay.resize(420, 360)
        self.overlay.show()
        self.requested: list[int] = []
        self.overlay.art_wanted.connect(
            lambda _kind, champion_id: self.requested.append(champion_id)
        )

    def tearDown(self):
        self.overlay.hide()

    def test_the_whole_roster_is_listed(self):
        self.overlay.open_for("Choose your champion")

        self.assertEqual(self.overlay.results.count(), self.ROSTER)

    def test_the_list_can_be_scrolled(self):
        self.overlay.open_for("Choose your champion")
        self.app.processEvents()

        bar = self.overlay.results.verticalScrollBar()

        self.assertGreater(bar.maximum(), 0, "the roster fits on screen, so nothing scrolls")
        self.assertTrue(bar.isVisibleTo(self.overlay))

    def test_only_the_icons_near_the_top_are_asked_for(self):
        self.overlay.open_for("Choose your champion")

        self.assertLess(len(self.requested), self.ROSTER)
        self.assertIn(self.catalog.all[0].id, self.requested)
        self.assertNotIn(self.catalog.all[-1].id, self.requested)

    def test_scrolling_asks_for_the_icons_that_come_into_view(self):
        self.overlay.open_for("Choose your champion")
        self.app.processEvents()
        first_batch = list(self.requested)

        bar = self.overlay.results.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.app.processEvents()

        self.assertGreater(len(self.requested), len(first_batch))
        self.assertIn(self.catalog.all[-1].id, self.requested)

    def test_an_icon_is_never_asked_for_twice(self):
        self.overlay.open_for("Choose your champion")
        bar = self.overlay.results.verticalScrollBar()
        for value in (bar.maximum() // 2, 0, bar.maximum(), 0):
            bar.setValue(value)
            self.app.processEvents()

        self.assertEqual(len(self.requested), len(set(self.requested)))


if __name__ == "__main__":
    unittest.main()
