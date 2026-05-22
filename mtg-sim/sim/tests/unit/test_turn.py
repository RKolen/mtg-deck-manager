"""Unit tests for engine/core/turn_structure.py and engine/core/priority.py."""

from engine.core.priority import PassResult, PriorityTracker
from engine.core.turn_structure import (
    Phase,
    PriorityPassOutcome,
    Step,
    TurnRunner,
    has_priority,
    is_main_phase,
    next_step,
    phase_of,
)


# ---------------------------------------------------------------------------
# Step metadata
# ---------------------------------------------------------------------------

def test_untap_has_no_priority():
    """Untap step grants no priority window (CR 502)."""
    assert not has_priority(Step.UNTAP)


def test_cleanup_has_no_priority():
    """Cleanup step grants no priority window unless SBAs or triggers occur (CR 514)."""
    assert not has_priority(Step.CLEANUP)


def test_upkeep_has_priority():
    """Upkeep is a normal priority step."""
    assert has_priority(Step.UPKEEP)


def test_declare_attackers_has_priority():
    """Declare attackers step has a priority window after attackers are chosen."""
    assert has_priority(Step.DECLARE_ATTACKERS)


def test_precombat_main_is_main_phase():
    """Precombat main phase allows sorcery-speed casts."""
    assert is_main_phase(Step.PRECOMBAT_MAIN)


def test_postcombat_main_is_main_phase():
    """Postcombat main phase allows sorcery-speed casts."""
    assert is_main_phase(Step.POSTCOMBAT_MAIN)


def test_upkeep_is_not_main_phase():
    """Upkeep is not a main phase; sorcery-speed casts are not allowed."""
    assert not is_main_phase(Step.UPKEEP)


def test_phase_of_untap():
    """Untap belongs to the Beginning phase."""
    assert phase_of(Step.UNTAP) == Phase.BEGINNING


def test_phase_of_declare_attackers():
    """Declare attackers belongs to the Combat phase."""
    assert phase_of(Step.DECLARE_ATTACKERS) == Phase.COMBAT


def test_phase_of_end_step():
    """End step belongs to the Ending phase."""
    assert phase_of(Step.END_STEP) == Phase.ENDING


# ---------------------------------------------------------------------------
# next_step ordering
# ---------------------------------------------------------------------------

def test_next_step_from_untap():
    """Untap is followed by Upkeep."""
    assert next_step(Step.UNTAP) == Step.UPKEEP


def test_next_step_from_draw():
    """Draw step is followed by Precombat Main."""
    assert next_step(Step.DRAW) == Step.PRECOMBAT_MAIN


def test_next_step_skips_first_strike_by_default():
    """Without first-strike flag, Declare Blockers goes straight to Regular Damage."""
    assert next_step(Step.DECLARE_BLOCKERS) == Step.REGULAR_DAMAGE


def test_next_step_inserts_first_strike_when_flagged():
    """First-strike damage step is inserted when include_first_strike=True."""
    assert next_step(Step.DECLARE_BLOCKERS, include_first_strike=True) == Step.FIRST_STRIKE_DAMAGE


def test_next_step_from_first_strike_goes_to_regular():
    """First Strike Damage is always followed by Regular Damage."""
    assert next_step(Step.FIRST_STRIKE_DAMAGE) == Step.REGULAR_DAMAGE


def test_next_step_cleanup_returns_none():
    """Cleanup is the last step; next_step returns None to signal turn end."""
    assert next_step(Step.CLEANUP) is None


def test_full_turn_step_sequence():
    """Walking every next_step from UNTAP produces the canonical 12-step sequence."""
    expected = [
        Step.UNTAP, Step.UPKEEP, Step.DRAW, Step.PRECOMBAT_MAIN,
        Step.BEGIN_COMBAT, Step.DECLARE_ATTACKERS, Step.DECLARE_BLOCKERS,
        Step.REGULAR_DAMAGE, Step.END_COMBAT, Step.POSTCOMBAT_MAIN,
        Step.END_STEP, Step.CLEANUP,
    ]
    current = Step.UNTAP
    actual = [current]
    while True:
        nxt = next_step(current)
        if nxt is None:
            break
        actual.append(nxt)
        current = nxt
    assert actual == expected


# ---------------------------------------------------------------------------
# PriorityTracker
# ---------------------------------------------------------------------------

def test_priority_starts_with_active_player():
    """reset() gives priority to the active player."""
    pt = PriorityTracker(active_player_idx=0)
    pt.reset()
    assert pt.priority_holder_idx == 0


def test_first_pass_transfers_priority():
    """First pass gives priority to the non-active player and returns PRIORITY_TRANSFERRED."""
    pt = PriorityTracker(active_player_idx=0)
    pt.reset()
    result = pt.pass_priority()
    assert result == PassResult.PRIORITY_TRANSFERRED
    assert pt.priority_holder_idx == 1


def test_second_pass_signals_both_passed():
    """Two consecutive passes without action return BOTH_PASSED."""
    pt = PriorityTracker(active_player_idx=0)
    pt.reset()
    pt.pass_priority()
    result = pt.pass_priority()
    assert result == PassResult.BOTH_PASSED


def test_action_taken_resets_pass_count():
    """action_taken resets the pass counter so the next pass is again a first pass."""
    pt = PriorityTracker(active_player_idx=0)
    pt.reset()
    pt.pass_priority()
    pt.action_taken()
    result = pt.pass_priority()
    assert result == PassResult.PRIORITY_TRANSFERRED


def test_holder_is_active_initially():
    """After reset the active player holds priority."""
    pt = PriorityTracker(active_player_idx=1)
    pt.reset()
    assert pt.holder_is_active()


def test_can_auto_pass_when_no_action():
    """can_auto_pass returns True when the holder has no legal instant-speed action."""
    pt = PriorityTracker()
    assert pt.can_auto_pass(has_instant_speed_action=False)
    assert not pt.can_auto_pass(has_instant_speed_action=True)


# ---------------------------------------------------------------------------
# TurnRunner
# ---------------------------------------------------------------------------

def test_begin_turn_sets_untap():
    """begin_turn starts at the Untap step."""
    runner = TurnRunner()
    runner.begin_turn(active_player_idx=0)
    assert runner.current_step == Step.UNTAP


def test_auto_advance_untap_goes_to_upkeep():
    """auto_advance_untap moves immediately to Upkeep without a priority window."""
    runner = TurnRunner()
    runner.begin_turn(0)
    step = runner.auto_advance_untap()
    assert step == Step.UPKEEP


def test_pass_priority_transfers():
    """First priority pass at Upkeep transfers to the non-active player."""
    runner = TurnRunner()
    runner.begin_turn(0)
    runner.auto_advance_untap()
    outcome = runner.pass_priority(stack_is_empty=True)
    assert outcome == PriorityPassOutcome.PRIORITY_TRANSFERRED


def test_both_pass_empty_stack_advances_step():
    """Both players passing with an empty stack advances from Upkeep to Draw."""
    runner = TurnRunner()
    runner.begin_turn(0)
    runner.auto_advance_untap()
    runner.pass_priority(stack_is_empty=True)
    outcome = runner.pass_priority(stack_is_empty=True)
    assert outcome == PriorityPassOutcome.ADVANCE_STEP
    assert runner.current_step == Step.DRAW


def test_both_pass_non_empty_stack_resolves_top():
    """Both players passing with objects on the stack signals RESOLVE_TOP."""
    runner = TurnRunner()
    runner.begin_turn(0)
    runner.auto_advance_untap()
    runner.pass_priority(stack_is_empty=False)
    outcome = runner.pass_priority(stack_is_empty=False)
    assert outcome == PriorityPassOutcome.RESOLVE_TOP


def test_turn_ended_at_cleanup():
    """Both players passing at Cleanup signals TURN_ENDED and increments turn number."""
    runner = TurnRunner()
    runner.begin_turn(0)
    runner.context.step = Step.CLEANUP
    runner.pass_priority(stack_is_empty=True)
    outcome = runner.pass_priority(stack_is_empty=True)
    assert outcome == PriorityPassOutcome.TURN_ENDED
    assert runner.context.turn_number == 2


def test_first_strike_step_inserted():
    """first_strike_in_combat=True inserts FIRST_STRIKE_DAMAGE after DECLARE_BLOCKERS."""
    runner = TurnRunner()
    runner.begin_turn(0)
    runner.context.step = Step.DECLARE_BLOCKERS
    runner.first_strike_in_combat = True
    runner.pass_priority(stack_is_empty=True)
    runner.pass_priority(stack_is_empty=True)
    assert runner.current_step == Step.FIRST_STRIKE_DAMAGE


def test_first_strike_step_not_inserted_without_flag():
    """first_strike_in_combat=False goes directly from DECLARE_BLOCKERS to REGULAR_DAMAGE."""
    runner = TurnRunner()
    runner.begin_turn(0)
    runner.context.step = Step.DECLARE_BLOCKERS
    runner.first_strike_in_combat = False
    runner.pass_priority(stack_is_empty=True)
    runner.pass_priority(stack_is_empty=True)
    assert runner.current_step == Step.REGULAR_DAMAGE


def test_action_taken_resets_after_spell_on_stack():
    """After action_taken, the active player holds priority; first pass transfers it."""
    runner = TurnRunner()
    runner.begin_turn(0)
    runner.auto_advance_untap()
    runner.pass_priority(stack_is_empty=True)
    runner.action_taken()
    assert runner.priority.priority_holder_idx == runner.active_player_idx
    outcome = runner.pass_priority(stack_is_empty=True)
    assert outcome == PriorityPassOutcome.PRIORITY_TRANSFERRED


def test_to_dict_contains_required_keys():
    """to_dict includes all keys needed by the frontend."""
    runner = TurnRunner()
    runner.begin_turn(0)
    d = runner.to_dict()
    for key in ("turnNumber", "step", "phase", "activePlayer", "priorityHolder"):
        assert key in d
