"""Shared face-down turn-up timing checks."""

from __future__ import annotations

from collections.abc import Callable

from deck_registry import CardInfo
from engine.core.game_object import Permanent
from engine.core.game_state import GameState


def can_turn_up_face_down_keyword(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
    has_keyword: Callable[[CardInfo], bool],
) -> bool:
    """Return True when a face-down creature may be turned face up."""
    if perm.controller_idx != controller_idx or not perm.face_down:
        return False
    if perm.card_info is None or not has_keyword(perm.card_info):
        return False
    if not game.stack.is_empty:
        return False
    return phase in ('main1', 'main2')
