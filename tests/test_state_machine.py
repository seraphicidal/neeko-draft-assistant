"""The decisions: when to act, when to hold still, and when to give up.

Every failsafe the assistant promises is pinned down here.
"""

import unittest

from league import champion_select as cs
from league.matchmaking import ReadyCheck
from core.state_machine import AppState, Intent, IntentKind, Snapshot, StateMachine
from tests.mocks import FakeSettings, action, ready_check_payload, session_payload

AHRI, NEEKO, LUX = 103, 518, 99


def pop(response="None", state="InProgress", timer=1.0) -> ReadyCheck:
    return ReadyCheck.parse(ready_check_payload(response=response, state=state, timer=timer))


def no_pop() -> ReadyCheck:
    """What the ready-check endpoint answers when nothing is being asked."""
    return pop(state="Invalid", timer=0.0)


def draft(**kwargs) -> cs.Session:
    return cs.Session.parse(session_payload(**kwargs))


def snap(now=0.0, **kwargs) -> Snapshot:
    kwargs.setdefault("connected", True)
    kwargs.setdefault("phase", "ChampSelect" if kwargs.get("session") else "None")
    return Snapshot(now=now, **kwargs)


def kinds(decision) -> list[IntentKind]:
    return [intent.kind for intent in decision.intents]


def succeed(machine: StateMachine, decision, now=0.0) -> None:
    """Play the watcher: report every intent as having worked."""
    for intent in decision.intents:
        machine.record_result(intent, True, now)


def fail(machine: StateMachine, decision, now=0.0) -> None:
    for intent in decision.intents:
        machine.record_result(intent, False, now)


class PhaseTest(unittest.TestCase):
    def test_no_client_means_disconnected(self):
        decision = StateMachine().decide(Snapshot(now=0.0, connected=False), FakeSettings())

        self.assertEqual(decision.state, AppState.DISCONNECTED)
        self.assertEqual(decision.intents, ())

    def test_plain_phases_map_to_states(self):
        machine = StateMachine()
        for phase, expected in [
            ("Lobby", AppState.LOBBY),
            ("Matchmaking", AppState.QUEUED),
            ("InProgress", AppState.IN_GAME),
            ("EndOfGame", AppState.POST_GAME),
            ("None", AppState.WAITING),
        ]:
            with self.subTest(phase=phase):
                self.assertEqual(machine.decide(snap(phase=phase), FakeSettings()).state, expected)


class QueueTest(unittest.TestCase):
    def test_a_pop_asks_for_an_accept(self):
        decision = StateMachine().decide(snap(ready_check=pop(), phase="ReadyCheck"), FakeSettings())

        self.assertEqual(decision.state, AppState.READY_CHECK)
        self.assertEqual(kinds(decision), [IntentKind.ACCEPT_READY_CHECK])

    def test_accept_is_asked_for_only_once(self):
        machine, settings = StateMachine(), FakeSettings()
        first = machine.decide(snap(ready_check=pop()), settings)
        succeed(machine, first)

        again = machine.decide(snap(now=0.3, ready_check=pop()), settings)

        self.assertEqual(kinds(again), [])

    def test_delay_holds_the_accept_back(self):
        machine, settings = StateMachine(), FakeSettings(accept_delay=3.0)

        early = machine.decide(snap(now=100.0, ready_check=pop()), settings)
        self.assertEqual(kinds(early), [])
        self.assertIn("Accepting in", early.detail)

        late = machine.decide(snap(now=103.5, ready_check=pop()), settings)
        self.assertEqual(kinds(late), [IntentKind.ACCEPT_READY_CHECK])

    def test_auto_accept_off_does_nothing(self):
        decision = StateMachine().decide(snap(ready_check=pop()), FakeSettings(auto_accept=False))

        self.assertEqual(kinds(decision), [])
        self.assertIn("off", decision.detail)

    def test_answering_by_hand_is_respected(self):
        machine = StateMachine()

        for response, expected in (("Accepted", "accepted"), ("Declined", "declined")):
            with self.subTest(response=response):
                decision = machine.decide(snap(ready_check=pop(response)), FakeSettings())
                self.assertEqual(decision.state, AppState.ACCEPTED)
                self.assertEqual(kinds(decision), [])
                self.assertIn(expected, decision.detail)

    def test_accept_gives_up_after_three_failures(self):
        machine, settings = StateMachine(), FakeSettings()
        now = 0.0
        for _ in range(3):
            decision = machine.decide(snap(now=now, ready_check=pop()), settings)
            fail(machine, decision, now)
            now += 10.0  # push past the backoff each time

        final = machine.decide(snap(now=now, ready_check=pop()), settings)

        self.assertEqual(kinds(final), [])
        self.assertIn("refused", final.problem)

    def test_backoff_pauses_between_failures(self):
        machine, settings = StateMachine(), FakeSettings()
        first = machine.decide(snap(now=0.0, ready_check=pop()), settings)
        fail(machine, first, 0.0)

        immediately = machine.decide(snap(now=0.2, ready_check=pop()), settings)
        self.assertEqual(kinds(immediately), [])

        after_backoff = machine.decide(snap(now=1.5, ready_check=pop()), settings)
        self.assertEqual(kinds(after_backoff), [IntentKind.ACCEPT_READY_CHECK])

    def test_the_endpoint_answering_between_pops_is_not_a_pop(self):
        # The client serves the ready-check endpoint at all times; with no
        # match on offer it reads `Invalid`. Treating that as a pop is what
        # used to leave the app saying "match found" for a whole queue.
        decision = StateMachine().decide(
            snap(ready_check=no_pop(), phase="Matchmaking"), FakeSettings()
        )

        self.assertEqual(decision.state, AppState.QUEUED)
        self.assertEqual(kinds(decision), [])

    def test_a_declined_match_leaves_the_accept_armed(self):
        # When a match is declined the client drops everyone straight back
        # into the queue without ever leaving the matchmaking phase. The
        # accept has to be armed again anyway, or it is spent for the session.
        machine, settings = StateMachine(), FakeSettings()
        succeed(machine, machine.decide(snap(now=1.0, ready_check=pop()), settings))
        machine.decide(snap(now=2.0, ready_check=pop("Accepted")), settings)

        machine.decide(snap(now=8.0, phase="Matchmaking", ready_check=no_pop()), settings)
        again = machine.decide(snap(now=30.0, phase="ReadyCheck", ready_check=pop()), settings)

        self.assertEqual(kinds(again), [IntentKind.ACCEPT_READY_CHECK])

    def test_a_second_pop_caught_without_a_gap_is_still_a_second_pop(self):
        machine, settings = StateMachine(), FakeSettings()
        succeed(machine, machine.decide(snap(now=1.0, ready_check=pop(timer=8.0)), settings))

        restarted = machine.decide(snap(now=20.0, ready_check=pop(timer=0.4)), settings)

        self.assertEqual(kinds(restarted), [IntentKind.ACCEPT_READY_CHECK])

    def test_the_delay_is_counted_again_for_the_next_pop(self):
        machine, settings = StateMachine(), FakeSettings(accept_delay=3.0)
        machine.decide(snap(now=10.0, ready_check=pop()), settings)
        succeed(machine, machine.decide(snap(now=13.5, ready_check=pop()), settings))
        machine.decide(snap(now=20.0, phase="Matchmaking", ready_check=no_pop()), settings)

        immediately = machine.decide(snap(now=60.0, ready_check=pop()), settings)
        after_the_wait = machine.decide(snap(now=63.5, ready_check=pop()), settings)

        self.assertEqual(kinds(immediately), [], "the second pop skipped its delay")
        self.assertEqual(kinds(after_the_wait), [IntentKind.ACCEPT_READY_CHECK])

    def test_a_new_pop_may_be_accepted_again(self):
        machine, settings = StateMachine(), FakeSettings()
        succeed(machine, machine.decide(snap(ready_check=pop()), settings))

        machine.decide(snap(now=5.0, phase="Lobby"), settings)  # pop gone
        decision = machine.decide(snap(now=9.0, ready_check=pop()), settings)

        self.assertEqual(kinds(decision), [IntentKind.ACCEPT_READY_CHECK])


class DraftDetectionTest(unittest.TestCase):
    def test_planning_phase_is_champ_select(self):
        decision = StateMachine().decide(snap(session=draft(phase=cs.PLANNING)), FakeSettings())

        self.assertEqual(decision.state, AppState.CHAMP_SELECT)

    def test_someone_elses_turn_is_a_wait(self):
        session = draft(local_cell=2, actions=[[action(1, cell=1, in_progress=True), action(2, cell=2)]])

        decision = StateMachine().decide(snap(session=session), FakeSettings())

        self.assertEqual(decision.state, AppState.WAITING_FOR_MY_TURN)

    def test_my_pick_turn_is_reported(self):
        session = draft(local_cell=2, actions=[[action(2, cell=2, in_progress=True)]])

        decision = StateMachine().decide(snap(session=session), FakeSettings(preferred_champion_id=NEEKO))

        self.assertEqual(decision.state, AppState.MY_TURN)
        self.assertEqual(decision.turn, "PICK")

    def test_my_ban_turn_never_produces_a_pick(self):
        session = draft(local_cell=2, actions=[[action(2, cell=2, kind="ban", in_progress=True)]])

        decision = StateMachine().decide(
            snap(session=session), FakeSettings(preferred_champion_id=NEEKO)
        )

        self.assertEqual(decision.turn, "BAN")
        self.assertNotIn(IntentKind.LOCK_CHAMPION, kinds(decision))

    def test_locked_in_is_a_state_of_its_own(self):
        session = draft(local_cell=2, actions=[[action(2, cell=2, champion=NEEKO, completed=True)]])

        decision = StateMachine().decide(
            snap(session=session), FakeSettings(preferred_champion_id=NEEKO)
        )

        self.assertEqual(decision.state, AppState.LOCKED)
        self.assertEqual(kinds(decision), [])


class DeclareTest(unittest.TestCase):
    def setUp(self):
        self.session = draft(local_cell=2, actions=[[action(5, cell=2)]])

    def test_declares_the_preferred_champion(self):
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_pick=False)

        decision = StateMachine().decide(snap(session=self.session), settings)

        self.assertEqual(kinds(decision), [IntentKind.DECLARE_CHAMPION])
        self.assertEqual(decision.intents[0].champion_id, NEEKO)
        self.assertEqual(decision.intents[0].action_id, 5)

    def test_declares_only_once(self):
        machine = StateMachine()
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_pick=False)
        succeed(machine, machine.decide(snap(session=self.session), settings))

        again = machine.decide(snap(now=1.0, session=self.session), settings)

        self.assertEqual(kinds(again), [])

    def test_a_hover_made_by_hand_is_left_alone(self):
        session = draft(local_cell=2, actions=[[action(5, cell=2)]], pick_intent=NEEKO)
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_pick=False)

        decision = StateMachine().decide(snap(session=session), settings)

        self.assertEqual(kinds(decision), [])

    def test_auto_declare_off_stays_quiet(self):
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_declare=False, auto_pick=False)

        self.assertEqual(kinds(StateMachine().decide(snap(session=self.session), settings)), [])

    def test_declare_gives_up_after_three_failures(self):
        machine = StateMachine()
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_pick=False)
        now = 0.0
        for _ in range(3):
            fail(machine, machine.decide(snap(now=now, session=self.session), settings), now)
            now += 10.0

        final = machine.decide(snap(now=now, session=self.session), settings)

        self.assertEqual(kinds(final), [])
        self.assertIn("declare", final.problem)


class PickTest(unittest.TestCase):
    def my_turn(self):
        return draft(local_cell=2, actions=[[action(5, cell=2, in_progress=True)]])

    def test_locks_in_on_my_turn(self):
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_declare=False)

        decision = StateMachine().decide(snap(session=self.my_turn()), settings)

        self.assertEqual(kinds(decision), [IntentKind.LOCK_CHAMPION])
        self.assertEqual(decision.intents[0].champion_id, NEEKO)

    def test_never_locks_before_my_turn(self):
        session = draft(local_cell=2, actions=[[action(5, cell=2, in_progress=False)]])
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_declare=False)

        decision = StateMachine().decide(snap(session=session), settings)

        self.assertEqual(kinds(decision), [])

    def test_auto_pick_off_only_declares(self):
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_pick=False)

        decision = StateMachine().decide(snap(session=self.my_turn()), settings)

        self.assertEqual(kinds(decision), [IntentKind.DECLARE_CHAMPION])

    def test_locks_in_only_once(self):
        machine = StateMachine()
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_declare=False)
        succeed(machine, machine.decide(snap(session=self.my_turn()), settings))

        again = machine.decide(snap(now=0.5, session=self.my_turn()), settings)

        self.assertEqual(kinds(again), [])


class AvailabilityTest(unittest.TestCase):
    def test_a_banned_champion_is_not_picked(self):
        session = draft(
            local_cell=2,
            actions=[[action(1, cell=7, kind="ban", champion=NEEKO, completed=True),
                      action(5, cell=2, in_progress=True)]],
        )
        settings = FakeSettings(preferred_champion_id=NEEKO)

        decision = StateMachine().decide(snap(session=session), settings)

        self.assertEqual(kinds(decision), [])
        self.assertIn("banned", decision.problem)

    def test_falls_back_to_the_backup_champion(self):
        session = draft(
            local_cell=2,
            actions=[[action(1, cell=7, kind="ban", champion=NEEKO, completed=True),
                      action(5, cell=2, in_progress=True)]],
        )
        settings = FakeSettings(preferred_champion_id=NEEKO, backup_champion_id=AHRI)

        decision = StateMachine().decide(snap(session=session), settings)

        self.assertEqual(
            [intent.champion_id for intent in decision.intents if intent.champion_id], [AHRI, AHRI]
        )

    def test_no_champion_available_means_no_action_at_all(self):
        # The whole point: never substitute a champion the user did not name.
        session = draft(
            local_cell=2,
            actions=[[action(1, cell=7, kind="ban", champion=NEEKO, completed=True),
                      action(2, cell=8, kind="ban", champion=AHRI, completed=True),
                      action(5, cell=2, in_progress=True)]],
        )
        settings = FakeSettings(preferred_champion_id=NEEKO, backup_champion_id=AHRI)

        decision = StateMachine().decide(snap(session=session), settings)

        self.assertEqual(kinds(decision), [])
        self.assertTrue(decision.problem)

    def test_no_champion_configured_says_so(self):
        session = draft(local_cell=2, actions=[[action(5, cell=2, in_progress=True)]])

        decision = StateMachine().decide(snap(session=session), FakeSettings())

        self.assertEqual(kinds(decision), [])
        self.assertIn("No champion", decision.problem)

    def test_the_pickable_list_is_obeyed(self):
        session = draft(local_cell=2, actions=[[action(5, cell=2, in_progress=True)]])
        settings = FakeSettings(preferred_champion_id=NEEKO)

        decision = StateMachine().decide(
            snap(session=session, pickable=frozenset({AHRI, LUX})), settings
        )

        self.assertEqual(kinds(decision), [])
        self.assertIn("not available", decision.problem)

    def test_an_empty_pickable_list_is_unknown_not_forbidden(self):
        # The endpoint 404s outside a draft; that must not block everything.
        session = draft(local_cell=2, actions=[[action(5, cell=2, in_progress=True)]])
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_declare=False)

        decision = StateMachine().decide(snap(session=session, pickable=frozenset()), settings)

        self.assertEqual(kinds(decision), [IntentKind.LOCK_CHAMPION])


class ChatTest(unittest.TestCase):
    def settings(self, **overrides):
        return FakeSettings(
            **{
                "chat_enabled": True,
                "chat_message": "hello gl hf",
                "auto_declare": False,
                "auto_pick": False,
                **overrides,
            }
        )

    def test_sends_the_message_once_the_room_is_ready(self):
        decision = StateMachine().decide(
            snap(session=draft(), chat_ready=True), self.settings()
        )

        self.assertEqual(kinds(decision), [IntentKind.SEND_CHAT])
        self.assertEqual(decision.intents[0].message, "hello gl hf")

    def test_waits_for_the_room(self):
        decision = StateMachine().decide(snap(session=draft(), chat_ready=False), self.settings())

        self.assertEqual(kinds(decision), [])

    def test_sends_only_once_per_draft(self):
        machine, settings = StateMachine(), self.settings()
        succeed(machine, machine.decide(snap(session=draft(), chat_ready=True), settings))

        again = machine.decide(snap(now=1.0, session=draft(), chat_ready=True), settings)

        self.assertEqual(kinds(again), [])
        self.assertTrue(machine.chat_sent)

    def test_sends_again_in_the_next_draft(self):
        machine, settings = StateMachine(), self.settings()
        succeed(machine, machine.decide(snap(session=draft(chat_id="room-1"), chat_ready=True), settings))

        machine.decide(snap(now=60.0, phase="InProgress"), settings)  # draft over
        decision = machine.decide(
            snap(now=300.0, session=draft(chat_id="room-2"), chat_ready=True), settings
        )

        self.assertEqual(kinds(decision), [IntentKind.SEND_CHAT])

    def test_disabled_or_empty_message_sends_nothing(self):
        for settings in (self.settings(chat_enabled=False), self.settings(chat_message="   ")):
            with self.subTest(settings=settings.chat_message):
                decision = StateMachine().decide(snap(session=draft(), chat_ready=True), settings)
                self.assertEqual(kinds(decision), [])

    def test_gives_up_after_three_failures_without_spamming(self):
        machine, settings = StateMachine(), self.settings()
        now = 0.0
        for _ in range(3):
            fail(machine, machine.decide(snap(now=now, session=draft(), chat_ready=True), settings), now)
            now += 10.0

        final = machine.decide(snap(now=now, session=draft(), chat_ready=True), settings)

        self.assertEqual(kinds(final), [])
        self.assertTrue(machine.chat_failed)
        self.assertIn("draft message", final.problem)


class SessionResetTest(unittest.TestCase):
    def test_a_new_draft_re_arms_everything(self):
        machine = StateMachine()
        settings = FakeSettings(
            preferred_champion_id=NEEKO, chat_enabled=True, chat_message="hi", auto_pick=False
        )
        first = draft(chat_id="room-1", local_cell=2, actions=[[action(5, cell=2)]])
        succeed(machine, machine.decide(snap(session=first, chat_ready=True), settings))

        second = draft(chat_id="room-2", local_cell=2, actions=[[action(9, cell=2)]])
        decision = machine.decide(snap(now=200.0, session=second, chat_ready=True), settings)

        self.assertEqual(
            sorted(kind.value for kind in kinds(decision)),
            ["DECLARE_CHAMPION", "SEND_CHAT"],
        )


class TransitionTest(unittest.TestCase):
    def test_a_whole_game_walks_the_expected_states(self):
        machine = StateMachine()
        settings = FakeSettings(preferred_champion_id=NEEKO)
        my_cell = [[action(5, cell=2)]]
        my_turn = [[action(5, cell=2, in_progress=True)]]
        locked = [[action(5, cell=2, champion=NEEKO, completed=True)]]

        steps = [
            (Snapshot(now=0.0, connected=False), AppState.DISCONNECTED),
            (snap(now=1.0, phase="Lobby"), AppState.LOBBY),
            (snap(now=2.0, phase="Matchmaking"), AppState.QUEUED),
            (snap(now=3.0, phase="ReadyCheck", ready_check=pop()), AppState.READY_CHECK),
            (snap(now=4.0, phase="ReadyCheck", ready_check=pop("Accepted")), AppState.ACCEPTED),
            (snap(now=5.0, session=draft(local_cell=2, actions=my_cell, phase=cs.PLANNING)),
             AppState.CHAMP_SELECT),
            (snap(now=6.0, session=draft(local_cell=2, actions=my_cell)),
             AppState.WAITING_FOR_MY_TURN),
            (snap(now=7.0, session=draft(local_cell=2, actions=my_turn)), AppState.MY_TURN),
            (snap(now=8.0, session=draft(local_cell=2, actions=locked)), AppState.LOCKED),
            (snap(now=9.0, phase="InProgress"), AppState.IN_GAME),
            (snap(now=10.0, phase="EndOfGame"), AppState.POST_GAME),
        ]

        seen = []
        for snapshot, expected in steps:
            decision = machine.decide(snapshot, settings)
            succeed(machine, decision, snapshot.now)
            seen.append(decision.state)
            self.assertEqual(decision.state, expected, f"at {snapshot.phase}")

        self.assertEqual(machine.state, AppState.POST_GAME)
        self.assertEqual(len(seen), len(steps))

    def test_losing_the_client_mid_draft_resets_cleanly(self):
        machine = StateMachine()
        settings = FakeSettings(preferred_champion_id=NEEKO, auto_pick=False)
        session = draft(local_cell=2, actions=[[action(5, cell=2)]])
        succeed(machine, machine.decide(snap(session=session), settings))

        machine.decide(Snapshot(now=10.0, connected=False), settings)
        back = machine.decide(snap(now=20.0, session=session), settings)

        # The client restarted, so the hover has to be made again.
        self.assertEqual(kinds(back), [IntentKind.DECLARE_CHAMPION])


if __name__ == "__main__":
    unittest.main()
