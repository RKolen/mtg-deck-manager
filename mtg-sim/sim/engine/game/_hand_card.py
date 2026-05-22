"""Shared hand/graveyard card lookup for game actions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager
from engine.game.helpers import require_card_info

if TYPE_CHECKING:
    from engine.game.runtime import GameRuntimeMixin


def hand_card_or_error(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
) -> tuple[CardObject | None, CardInfo | None, str | None]:
    """Return (card, card_info) or (None, None, error_message)."""
    hand = zones.player_zones[player_idx].hand
    if hand_idx < 0 or hand_idx >= len(hand):
        return None, None, f"Hand index {hand_idx} out of range"
    card = hand[hand_idx]
    if not isinstance(card, CardObject):
        return None, None, 'Invalid card'
    return card, require_card_info(card), None


def graveyard_card_or_error(
    zones: ZoneManager,
    player_idx: int,
    graveyard_idx: int,
) -> tuple[CardObject | None, CardInfo | None, str | None]:
    """Return (card, card_info) or (None, None, error_message)."""
    graveyard = zones.player_zones[player_idx].graveyard
    if graveyard_idx < 0 or graveyard_idx >= len(graveyard):
        return None, None, f"Graveyard index {graveyard_idx} out of range"
    card = graveyard[graveyard_idx]
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
