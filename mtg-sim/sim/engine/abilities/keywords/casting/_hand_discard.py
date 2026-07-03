"""Shared hand discard helpers for alternate casting costs."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from engine.abilities.activated._cost_keyword import discard_from_hand
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def hand_discard_error(
    zones: ZoneManager,
    player_idx: int,
    discard_hand_idx: int | None,
    *,
    missing_message: str,
    validate_card: Callable[[CardObject], str | None] | None = None,
) -> str | None:
    """Return an error when a hand discard payment is illegal."""
    if discard_hand_idx is None:
        return missing_message
    hand = zones.player_zones[player_idx].hand
    if discard_hand_idx < 0 or discard_hand_idx >= len(hand):
        return f"Discard hand index {discard_hand_idx} out of range"
    card = hand[discard_hand_idx]
    if not isinstance(card, CardObject):
        return "Cannot discard that object"
    if validate_card is not None:
        return validate_card(card)
    return None


def pop_hand_to_graveyard(
    zones: ZoneManager,
    player_idx: int,
    discard_hand_idx: int,
    game: GameState | None = None,
) -> CardObject:
    """Discard a card from hand to the graveyard."""
    return discard_from_hand(zones, player_idx, discard_hand_idx, game)


def discard_hand_card_name(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int | None,
    game: GameState | None = None,
) -> str | None:
    """Discard a hand card to the graveyard and return its name."""
    if hand_idx is None:
        return None
    hand = zones.player_zones[player_idx].hand
    if hand_idx < 0 or hand_idx >= len(hand):
        return None
    card = pop_hand_to_graveyard(zones, player_idx, hand_idx, game)
    return card.card_info.name if card.card_info is not None else '?'
