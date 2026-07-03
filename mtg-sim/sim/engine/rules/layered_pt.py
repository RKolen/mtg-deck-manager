"""Layered P/T entry points used by game_object without import cycles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.rules.continuous import effective_power as layered_power
from engine.rules.continuous import effective_toughness as layered_toughness

if TYPE_CHECKING:
    from engine.core.game_object import Permanent
    from engine.core.game_state import GameState


def effective_power(game: GameState, perm: Permanent) -> int:
    """Return layered combat power."""
    return layered_power(game, perm)


def effective_toughness(game: GameState, perm: Permanent) -> int:
    """Return layered toughness."""
    return layered_toughness(game, perm)
