"""Zone index lookups without importing the game helpers package."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager


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
    if card.card_info is None:
        return None, None, 'Invalid card'
    return card, card.card_info, None


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
    if card.card_info is None:
        return None, None, 'Invalid card'
    return card, card.card_info, None


def hand_card_with_info(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
) -> tuple[CardObject, CardInfo] | None:
    """Return (card, card_info) or None when the hand slot is invalid."""
    card, card_info, err = hand_card_or_error(zones, player_idx, hand_idx)
    if err is not None or card is None or card_info is None:
        return None
    return card, card_info


def graveyard_card_with_info(
    zones: ZoneManager,
    player_idx: int,
    graveyard_idx: int,
) -> tuple[CardObject, CardInfo] | None:
    """Return (card, card_info) or None when the graveyard slot is invalid."""
    card, card_info, err = graveyard_card_or_error(zones, player_idx, graveyard_idx)
    if err is not None or card is None or card_info is None:
        return None
    return card, card_info
