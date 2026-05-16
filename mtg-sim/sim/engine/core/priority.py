"""
Priority tracker for the MTG rules engine.

Priority determines which player may take an action at any given moment
(CR 117). The active player receives priority at the start of each step
(except Untap and Cleanup). When both players pass priority consecutively
the engine either resolves the top stack object or, if the stack is empty,
ends the current step.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class PassResult(enum.Enum):
    """Outcome returned by PriorityTracker.pass_priority."""

    PRIORITY_TRANSFERRED = "priority_transferred"
    BOTH_PASSED = "both_passed"


@dataclass
class PriorityTracker:
    """Tracks who holds priority and counts consecutive passes (CR 117).

    Callers must call:
      - reset()        when a new step begins or a spell/ability resolves
      - action_taken() whenever any player puts something on the stack
      - pass_priority() when the current holder explicitly passes

    The tracker is intentionally free of game-state knowledge; the caller
    decides what to do with BOTH_PASSED based on whether the stack is empty.
    """

    active_player_idx: int = 0
    priority_holder_idx: int = 0
    consecutive_passes: int = 0

    def reset(self, active_player_idx: int | None = None) -> None:
        """Give priority to the active player and clear the pass counter.

        Optionally updates which player is currently active (call this at
        the start of each step and after each spell or ability resolves).
        """
        if active_player_idx is not None:
            self.active_player_idx = active_player_idx
        self.priority_holder_idx = self.active_player_idx
        self.consecutive_passes = 0

    def action_taken(self) -> None:
        """Reset the pass counter after any player puts something on the stack.

        Per CR 117.3c, the active player receives priority after each spell
        or ability is put onto the stack. Callers must then give_priority_to
        the active player and call this method.
        """
        self.consecutive_passes = 0

    def pass_priority(self) -> PassResult:
        """The current holder passes priority.

        Returns BOTH_PASSED when both players have passed consecutively,
        signalling the engine to either resolve the top stack object or
        advance to the next step (CR 117.4).
        Returns PRIORITY_TRANSFERRED when only one player has passed so far.
        """
        self.consecutive_passes += 1
        if self.consecutive_passes >= 2:
            return PassResult.BOTH_PASSED
        self.priority_holder_idx = 1 - self.priority_holder_idx
        return PassResult.PRIORITY_TRANSFERRED

    def give_priority_to(self, player_idx: int) -> None:
        """Directly assign priority to a specific player and clear passes.

        Used after a spell resolves: the active player receives priority
        regardless of who cast the spell.
        """
        self.priority_holder_idx = player_idx
        self.consecutive_passes = 0

    @property
    def non_active_player_idx(self) -> int:
        """The index of the player who is not currently active."""
        return 1 - self.active_player_idx

    def holder_is_active(self) -> bool:
        """True when the active player is currently holding priority."""
        return self.priority_holder_idx == self.active_player_idx

    def can_auto_pass(self, has_instant_speed_action: bool) -> bool:
        """True when the engine may pass on the holder's behalf.

        The engine auto-passes when the holder has no legal instant-speed
        actions: no instants or flash spells they can afford, and no
        activated abilities available. The caller evaluates legality.
        """
        return not has_instant_speed_action

    def to_dict(self) -> dict:
        """Serialise priority state for the frontend."""
        return {
            "activePlayer": self.active_player_idx,
            "priorityHolder": self.priority_holder_idx,
            "consecutivePasses": self.consecutive_passes,
        }
