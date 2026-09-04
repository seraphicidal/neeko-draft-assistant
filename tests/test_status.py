"""The presentation layer's own rules.

`ui/status.py` is what turns a state machine decision into something a person
can read. It holds no Qt, so the guarantees the interface depends on -- every
state has a description, every description points at art that exists -- can be
checked here rather than by looking at screenshots.
"""

import unittest

from core.state_machine import AppState
from ui import assets, status, theme

SCENES = {
    status.OFFLINE,
    status.IDLE,
    status.QUEUE,
    status.READY,
    status.DRAFT,
    status.GAME,
}

PALETTE = {
    value
    for name, value in vars(theme).items()
    if isinstance(value, str) and value.startswith("#") and name.isupper()
}


class CoverageTest(unittest.TestCase):
    def test_every_state_has_a_description(self):
        for state in AppState:
            with self.subTest(state=state.value):
                self.assertIn(state.value, status.BY_STATE)

    def test_an_unknown_state_still_describes_itself(self):
        described = status.for_state("SOMETHING_NEW")

        self.assertTrue(described.label)
        self.assertTrue(described.headline)
        self.assertIn(described.scene, SCENES)

    def test_every_description_is_complete(self):
        for state, described in status.BY_STATE.items():
            with self.subTest(state=state):
                self.assertTrue(described.label, "the pill needs a label")
                self.assertTrue(described.headline, "the stage needs a headline")
                self.assertTrue(described.detail, "a supporting line explains it")
                self.assertTrue(described.voice, "Neeko always has something to say")

    def test_every_scene_is_one_the_stage_can_show(self):
        for state, described in status.BY_STATE.items():
            with self.subTest(state=state):
                self.assertIn(described.scene, SCENES)

    def test_every_tone_comes_from_the_palette(self):
        # Colours are tokens, never one-off hex values.
        for state, described in status.BY_STATE.items():
            with self.subTest(state=state):
                self.assertIn(described.tone, PALETTE)

    def test_every_illustration_is_installed(self):
        for state, described in status.BY_STATE.items():
            with self.subTest(state=state):
                self.assertIn(described.art, assets.ART_SLOTS)
                self.assertIsNotNone(
                    assets.art(described.art), f"{described.art}.png is missing"
                )


class SceneChoiceTest(unittest.TestCase):
    def test_no_client_shows_the_empty_state(self):
        self.assertEqual(status.for_state("DISCONNECTED").scene, status.OFFLINE)

    def test_the_draft_states_share_one_scene(self):
        for state in ("CHAMP_SELECT", "WAITING_FOR_MY_TURN", "MY_TURN", "LOCKED"):
            with self.subTest(state=state):
                self.assertEqual(status.for_state(state).scene, status.DRAFT)

    def test_playing_gets_its_own_scene(self):
        self.assertEqual(status.for_state("IN_GAME").scene, status.GAME)

    def test_the_queue_pop_is_marked_out_in_orange(self):
        self.assertEqual(status.for_state("READY_CHECK").tone, theme.ACCENT)
        self.assertEqual(status.for_state("MY_TURN").tone, theme.ACCENT)

    def test_quiet_states_do_not_animate_the_dot(self):
        for state in ("DISCONNECTED", "IN_GAME", "POST_GAME"):
            with self.subTest(state=state):
                self.assertFalse(status.for_state(state).live)

    def test_states_worth_watching_do_animate(self):
        for state in ("QUEUED", "READY_CHECK", "MY_TURN"):
            with self.subTest(state=state):
                self.assertTrue(status.for_state(state).live)


class ReactionTest(unittest.TestCase):
    def test_an_accepted_queue_gets_a_reaction(self):
        reaction = status.for_action("Queue accepted")

        self.assertIsNotNone(reaction)
        self.assertEqual(reaction.tone, theme.SUCCESS)

    def test_a_hover_names_the_champion(self):
        reaction = status.for_action("Declared Neeko")

        self.assertIn("Neeko", reaction.voice)
        self.assertEqual(reaction.tone, theme.ACCENT)

    def test_a_lock_names_the_champion(self):
        self.assertIn("Ahri", status.for_action("Locked in Ahri").voice)

    def test_ordinary_messages_get_no_reaction(self):
        self.assertIsNone(status.for_action("League client connected"))


class WordingTest(unittest.TestCase):
    def test_internal_phrasing_is_rewritten_for_people(self):
        rewritten = status.humanise("The client refused the accept. Press it yourself.")

        self.assertIn("Accept", rewritten)
        self.assertNotEqual(rewritten, "The client refused the accept. Press it yourself.")

    def test_messages_that_already_read_well_are_left_alone(self):
        message = "Preferred champion is banned or already taken."

        self.assertEqual(status.humanise(message), message)

    def test_nothing_becomes_nothing(self):
        self.assertEqual(status.humanise(""), "")

    def test_no_message_leaks_an_endpoint_or_a_status_code(self):
        # A player should never be shown a route or an HTTP code.
        for described in status.BY_STATE.values():
            for line in (described.label, described.headline, described.detail, described.voice):
                with self.subTest(line=line):
                    self.assertNotIn("/lol-", line)
                    self.assertNotIn("404", line)
        for message in status._REWRITES.values():
            with self.subTest(message=message):
                self.assertNotIn("/lol-", message)


if __name__ == "__main__":
    unittest.main()
