"""
Turn structure for the MTG rules engine.

Defines the 13 steps and 5 phases of a Magic turn (CR 500–514), the ordering
rules between them, and a TurnRunner that manages advancement based on priority
outcomes from PriorityTracker.

Design contract:
  - TurnRunner holds no game-state (cards, life, battlefield). It only tracks
    structural position (step, turn number, whose turn it is).
  - Callers feed it priority-pass and stack-empty signals; it returns the
    action the game loop must take next.
  - The first-strike damage step is conditional: TurnRunner inserts it only
    when the caller sets first_strike_in_combat = True before combat damage.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from engine.core.priority import PassResult, PriorityTracker


# ---------------------------------------------------------------------------
# Step and Phase enumerations
# ---------------------------------------------------------------------------

class Step(enum.Enum):
    """The 13 named steps of a Magic turn (CR 500)."""

    UNTAP = "untap"
    UPKEEP = "upkeep"
    DRAW = "draw"
    PRECOMBAT_MAIN = "precombat_main"
    BEGIN_COMBAT = "begin_combat"
    DECLARE_ATTACKERS = "declare_attackers"
    DECLARE_BLOCKERS = "declare_blockers"
    FIRST_STRIKE_DAMAGE = "first_strike_damage"
    REGULAR_DAMAGE = "regular_damage"
    END_COMBAT = "end_combat"
    POSTCOMBAT_MAIN = "postcombat_main"
    END_STEP = "end_step"
    CLEANUP = "cleanup"


class Phase(enum.Enum):
    """The 5 phases grouping the 13 steps (CR 500)."""

    BEGINNING = "beginning"
    PRECOMBAT_MAIN = "precombat_main"
    COMBAT = "combat"
    POSTCOMBAT_MAIN = "postcombat_main"
    ENDING = "ending"


# ---------------------------------------------------------------------------
# Step metadata
# ---------------------------------------------------------------------------

_STEP_PHASE: dict[Step, Phase] = {
    Step.UNTAP:               Phase.BEGINNING,
    Step.UPKEEP:              Phase.BEGINNING,
    Step.DRAW:                Phase.BEGINNING,
    Step.PRECOMBAT_MAIN:      Phase.PRECOMBAT_MAIN,
    Step.BEGIN_COMBAT:        Phase.COMBAT,
    Step.DECLARE_ATTACKERS:   Phase.COMBAT,
    Step.DECLARE_BLOCKERS:    Phase.COMBAT,
    Step.FIRST_STRIKE_DAMAGE: Phase.COMBAT,
    Step.REGULAR_DAMAGE:      Phase.COMBAT,
    Step.END_COMBAT:          Phase.COMBAT,
    Step.POSTCOMBAT_MAIN:     Phase.POSTCOMBAT_MAIN,
    Step.END_STEP:            Phase.ENDING,
    Step.CLEANUP:             Phase.ENDING,
}

# Normal step sequence without the conditional first-strike step.
_STEP_ORDER: tuple[Step, ...] = (
    Step.UNTAP,
    Step.UPKEEP,
    Step.DRAW,
    Step.PRECOMBAT_MAIN,
    Step.BEGIN_COMBAT,
    Step.DECLARE_ATTACKERS,
    Step.DECLARE_BLOCKERS,
    Step.REGULAR_DAMAGE,
    Step.END_COMBAT,
    Step.POSTCOMBAT_MAIN,
    Step.END_STEP,
    Step.CLEANUP,
)

# Untap and Cleanup have no priority window (CR 502, 514).
_NO_PRIORITY_STEPS: frozenset[Step] = frozenset({Step.UNTAP, Step.CLEANUP})

# Steps where "at the beginning of X" triggered abilities fire (CR 603.6).
TRIGGER_STEPS: frozenset[Step] = frozenset({
    Step.UPKEEP,
    Step.BEGIN_COMBAT,
    Step.END_STEP,
    Step.CLEANUP,
})


def phase_of(step: Step) -> Phase:
    """Return the phase that contains the given step."""
    return _STEP_PHASE[step]


def has_priority(step: Step) -> bool:
    """Return True if players receive priority during this step (CR 117.3)."""
    return step not in _NO_PRIORITY_STEPS


def is_main_phase(step: Step) -> bool:
    """Return True for steps where sorcery-speed spells may be cast (CR 307.1)."""
    return step in (Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN)


def next_step(current: Step, include_first_strike: bool = False) -> Step | None:
    """Return the step that follows current, or None when the turn ends.

    include_first_strike inserts FIRST_STRIKE_DAMAGE between DECLARE_BLOCKERS
    and REGULAR_DAMAGE when at least one creature with first strike or double
    strike is involved in combat (CR 703.3).
    """
    if current == Step.DECLARE_BLOCKERS and include_first_strike:
        return Step.FIRST_STRIKE_DAMAGE
    if current == Step.FIRST_STRIKE_DAMAGE:
        return Step.REGULAR_DAMAGE
    idx = _STEP_ORDER.index(current)
    if idx + 1 >= len(_STEP_ORDER):
        return None
    return _STEP_ORDER[idx + 1]


# ---------------------------------------------------------------------------
# TurnContext — structural position snapshot
# ---------------------------------------------------------------------------

@dataclass
class TurnContext:
    """Structural position in the turn: turn number, active player, current step."""

    turn_number: int = 1
    active_player_idx: int = 0
    step: Step = Step.UNTAP

    @property
    def phase(self) -> Phase:
        """The phase that contains the current step."""
        return phase_of(self.step)

    @property
    def can_cast_sorcery(self) -> bool:
        """True when the stack is empty and the step allows sorcery-speed casts."""
        return is_main_phase(self.step)

    @property
    def in_combat(self) -> bool:
        """True for all combat steps."""
        return phase_of(self.step) == Phase.COMBAT

    def to_dict(self) -> dict:
        """Serialise for the frontend."""
        return {
            "turnNumber": self.turn_number,
            "activePlayer": self.active_player_idx,
            "step": self.step.value,
            "phase": self.phase.value,
            "canCastSorcery": self.can_cast_sorcery,
            "inCombat": self.in_combat,
        }


# ---------------------------------------------------------------------------
# PriorityPassOutcome — what the game loop must do after a pass
# ---------------------------------------------------------------------------

class PriorityPassOutcome(enum.Enum):
    """Instruction returned by TurnRunner.pass_priority to the game loop."""

    PRIORITY_TRANSFERRED = "priority_transferred"
    ADVANCE_STEP = "advance_step"
    RESOLVE_TOP = "resolve_top"
    TURN_ENDED = "turn_ended"


# ---------------------------------------------------------------------------
# TurnRunner — structural turn management
# ---------------------------------------------------------------------------

@dataclass
class TurnRunner:
    """Manages structural turn advancement independent of game state.

    The runner knows about steps, phases, and priority passing. It does not
    know about cards, permanents, or life totals — those live in game state.

    Usage pattern:
      runner.begin_turn(active_player_idx)
      # ... auto-advance untap, handle upkeep triggers, etc.
      outcome = runner.pass_priority(stack_is_empty=True)
      if outcome == PriorityPassOutcome.ADVANCE_STEP:
          new_step = runner.current_step  # read after advance
    """

    context: TurnContext = field(default_factory=TurnContext)
    priority: PriorityTracker = field(default_factory=PriorityTracker)
    first_strike_in_combat: bool = False

    @property
    def current_step(self) -> Step:
        """The step the game is currently in."""
        return self.context.step

    @property
    def active_player_idx(self) -> int:
        """Index of the player whose turn it is."""
        return self.context.active_player_idx

    def begin_turn(self, active_player_idx: int) -> None:
        """Start a new turn for the given player at the Untap step."""
        self.context.active_player_idx = active_player_idx
        self.context.step = Step.UNTAP
        self.first_strike_in_combat = False
        self.priority.reset(active_player_idx)

    def auto_advance_untap(self) -> Step:
        """Advance past Untap (no priority window); return the new step (Upkeep).

        The caller is responsible for untapping permanents before calling this.
        """
        assert self.context.step == Step.UNTAP
        self.context.step = Step.UPKEEP
        self.priority.reset()
        return self.context.step

    def pass_priority(self, stack_is_empty: bool) -> PriorityPassOutcome:
        """Process one priority pass from the current holder.

        Returns the action the game loop must perform:
          PRIORITY_TRANSFERRED — the other player now has priority; wait
          ADVANCE_STEP         — both passed, empty stack; advance the step
          RESOLVE_TOP          — both passed, stack not empty; resolve top
          TURN_ENDED           — both passed, Cleanup step finished
        """
        result = self.priority.pass_priority()
        if result != PassResult.BOTH_PASSED:
            return PriorityPassOutcome.PRIORITY_TRANSFERRED
        if not stack_is_empty:
            return PriorityPassOutcome.RESOLVE_TOP
        return self._advance_step()

    def action_taken(self) -> None:
        """Called after any player puts a spell or ability onto the stack.

        Resets the consecutive-pass counter; the active player receives
        priority after each spell or ability is announced (CR 117.3c).
        """
        self.priority.action_taken()
        self.priority.give_priority_to(self.context.active_player_idx)

    def after_resolution(self) -> None:
        """Called after the top stack object resolves.

        The active player receives priority again (CR 117.4).
        """
        self.priority.reset()

    def to_dict(self) -> dict:
        """Serialise runner state for the frontend."""
        return {
            **self.context.to_dict(),
            **self.priority.to_dict(),
            "firstStrikeInCombat": self.first_strike_in_combat,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _advance_step(self) -> PriorityPassOutcome:
        """Move to the next step; return TURN_ENDED when the turn is over."""
        new_step = next_step(
            self.context.step,
            include_first_strike=self.first_strike_in_combat,
        )
        if new_step is None:
            self.context.turn_number += 1
            return PriorityPassOutcome.TURN_ENDED
        self.context.step = new_step
        if has_priority(new_step):
            self.priority.reset()
        return PriorityPassOutcome.ADVANCE_STEP
