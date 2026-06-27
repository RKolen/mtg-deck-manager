"""Extort: drain opponents when you cast a spell."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_extort(perm: Permanent) -> bool:
    """Return True when the permanent has extort."""
    return has_keyword(perm, 'Extort')


def has_extort_card(card: CardInfo) -> bool:
    """Return True when the card has extort."""
    return has_registered_keyword(card.oracle_text, 'Extort')


def apply_extort_on_spell_cast(game: GameState, controller_idx: int) -> str | None:
    """Each extort permanent you control drains 1 life from each opponent (simplified)."""
    count = sum(
        1
        for perm in game.zones.battlefield
        if perm.controller_idx == controller_idx and has_extort(perm)
    )
    if count <= 0:
        return None
    opponent = 1 - controller_idx
    game.players[opponent].life -= count
    game.gain_life(controller_idx, count)
    return f"extort drained {count} (P{opponent + 1})"
