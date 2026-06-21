"""Graveyard and battlefield activation gates for the interactive game loop."""

from __future__ import annotations

from engine.abilities.keywords.casting.mayhem import can_cast_via_mayhem, has_mayhem
from engine.abilities.keywords.other.transmute import can_transmute
from engine.abilities.keywords.other.transfigure import can_transfigure
from engine.abilities.keywords.other.reconfigure import can_reconfigure
from engine.core.game_object import CardObject, Permanent
from engine.core.game_state import GameState
from engine.game.helpers import require_card_info


def graveyard_can_mayhem(
    graveyard: list,
    *,
    phase: str,
    stack_is_empty: bool,
    land_played: bool,
) -> bool:
    """Return True when a graveyard card can be cast for mayhem."""
    if not stack_is_empty or not land_played:
        return False
    return any(
        isinstance(c, CardObject)
        and has_mayhem(require_card_info(c))
        and can_cast_via_mayhem(
            require_card_info(c),
            phase,
            stack_is_empty,
            land_played=land_played,
        )
        for c in graveyard
    )


def battlefield_can_transmute(
    game: GameState,
    permanents: list[Permanent],
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when a permanent can activate transmute."""
    if not game.stack.is_empty:
        return False
    return any(can_transmute(perm, game, controller_idx, phase) for perm in permanents)


def battlefield_can_transfigure(
    game: GameState,
    permanents: list[Permanent],
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when a permanent can activate transfigure."""
    if not game.stack.is_empty:
        return False
    return any(can_transfigure(perm, game, controller_idx, phase) for perm in permanents)


def battlefield_can_reconfigure(
    game: GameState,
    permanents: list[Permanent],
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when a permanent can activate reconfigure."""
    if not game.stack.is_empty:
        return False
    return any(can_reconfigure(perm, game, controller_idx, phase) for perm in permanents)
