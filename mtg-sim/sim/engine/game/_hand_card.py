"""Shared hand/graveyard card lookup for game actions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.core.game_object import CardObject
from engine.core.zone_card_lookup import (
    graveyard_card_or_error,
    graveyard_card_with_info,
    hand_card_or_error,
    hand_card_with_info,
)
from engine.core.zones import ZoneManager
from engine.game.helpers import require_card_info

if TYPE_CHECKING:
    from engine.game.runtime import GameRuntimeMixin

__all__ = [
    'exile_card_or_error',
    'graveyard_card_object',
    'graveyard_card_or_error',
    'graveyard_card_with_info',
    'hand_card_object',
    'hand_card_or_error',
    'hand_card_with_info',
    'load_hand_card_for_action',
    'run_with_hand_card',
]


def graveyard_card_object(
    zones: ZoneManager,
    player_idx: int,
    graveyard_idx: int,
) -> CardObject | None:
    """Return a graveyard card or None when the index is invalid."""
    card, _, err = graveyard_card_or_error(zones, player_idx, graveyard_idx)
    return card if err is None else None


def hand_card_object(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
) -> CardObject | None:
    """Return a hand card or None when the index is invalid."""
    card, _, err = hand_card_or_error(zones, player_idx, hand_idx)
    return card if err is None else None


def exile_card_or_error(
    zones: ZoneManager,
    player_idx: int,
    exile_idx: int,
) -> tuple[CardObject | None, CardInfo | None, str | None]:
    """Return (card, card_info) or (None, None, error_message)."""
    exile = zones.player_zones[player_idx].exile
    if exile_idx < 0 or exile_idx >= len(exile):
        return None, None, f"Exile index {exile_idx} out of range"
    card = exile[exile_idx]
    if not isinstance(card, CardObject):
        return None, None, 'Invalid card'
    return card, require_card_info(card), None


def load_hand_card_for_action(
    game: GameRuntimeMixin,
    hand_idx: int,
    *,
    player_idx: int = 0,
) -> tuple[CardObject | None, CardInfo | None, dict | None]:
    """Return (card, card_info, None) or (None, None, client_error_dict)."""
    card, card_info, err = hand_card_or_error(game.state.zones, player_idx, hand_idx)
    if err:
        return None, None, {**game.to_client(), "error": err}
    return card, card_info, None


def run_with_hand_card(
    game: GameRuntimeMixin,
    hand_idx: int,
    action: Callable[[CardObject, CardInfo], dict],
    *,
    player_idx: int = 0,
) -> dict:
    """Load a hand card, then run action(card, card_info)."""
    card, card_info, err = load_hand_card_for_action(game, hand_idx, player_idx=player_idx)
    if err is not None:
        return err
    assert card is not None and card_info is not None
    return action(card, card_info)
