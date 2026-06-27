"""Ascend: gain the City's Blessing when you control ten permanents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_ascend(perm: Permanent) -> bool:
    """Return True when a permanent grants ascend."""
    return has_keyword(perm, 'Ascend')


def has_ascend_card(card: CardInfo) -> bool:
    """Return True when the card has ascend."""
    return has_registered_keyword(card.oracle_text, 'Ascend')


def update_ascend_status(game: GameState, player_idx: int) -> str | None:
    """Set ascended when the player controls ten or more permanents."""
    if game.players[player_idx].ascended:
        return None
    count = sum(
        1 for perm in game.zones.battlefield if perm.controller_idx == player_idx
    )
    if count < 10:
        return None
    game.players[player_idx].ascended = True
    return f"P{player_idx + 1} ascended (City's Blessing)"
