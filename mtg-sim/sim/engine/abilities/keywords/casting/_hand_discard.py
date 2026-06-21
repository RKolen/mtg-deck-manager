"""Shared hand discard helpers for alternate casting costs."""

from __future__ import annotations

from collections.abc import Callable

from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager


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
) -> CardObject:
    """Discard a card from hand to the graveyard."""
    hand = zones.player_zones[player_idx].hand
    card = hand.pop(discard_hand_idx)
    assert isinstance(card, CardObject)
    zones.player_zones[player_idx].graveyard.append(card)
    return card


def discard_hand_card_name(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int | None,
) -> str | None:
    """Discard a hand card to the graveyard and return its name."""
    if hand_idx is None:
        return None
    hand = zones.player_zones[player_idx].hand
    if hand_idx < 0 or hand_idx >= len(hand):
        return None
    card = pop_hand_to_graveyard(zones, player_idx, hand_idx)
    return card.card_info.name if card.card_info is not None else '?'
