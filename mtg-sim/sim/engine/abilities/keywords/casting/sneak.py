"""Sneak: exile lands from hand to reduce generic mana owed (CR 702.153, simplified)."""

from __future__ import annotations

from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager

SNEAK_MANA_PER_LAND = 2


@dataclass(frozen=True)
class SneakCastInput:
    """Hand indices for a sneak-assisted cast."""

    spell_hand_idx: int
    land_hand_indices: tuple[int, ...] = ()


def has_sneak(card: CardInfo) -> bool:
    """Return True when the card has sneak."""
    return has_registered_keyword(card.oracle_text, 'Sneak')


def has_sneak_card(card: CardInfo) -> bool:
    """Return True when the card has sneak."""
    return has_sneak(card)


def normalize_sneak_land_hand_indices(
    card: CardInfo,
    spell_hand_idx: int,
    land_hand_indices: list[int],
) -> list[int]:
    """Return deduped hand indices of lands to exile for sneak."""
    if not land_hand_indices or not has_sneak(card):
        return []
    seen: set[int] = set()
    unique: list[int] = []
    for idx in land_hand_indices:
        if idx != spell_hand_idx and idx not in seen:
            seen.add(idx)
            unique.append(idx)
    return unique


def _is_land_card(card: CardObject) -> bool:
    assert card.card_info is not None
    return card.card_info.is_land


def sneak_land_error(
    zones: ZoneManager,
    player_idx: int,
    spell_hand_idx: int,
    land_hand_indices: list[int],
) -> str | None:
    """Return an error message when sneak land choices are illegal."""
    hand = zones.player_zones[player_idx].hand
    for idx in land_hand_indices:
        if idx == spell_hand_idx:
            return "Cannot sneak-exile the spell being cast"
        if idx < 0 or idx >= len(hand):
            return f"Sneak hand index {idx} out of range"
        card = hand[idx]
        if not isinstance(card, CardObject):
            return f"Sneak index {idx} is not a card"
        if not _is_land_card(card):
            return f"Sneak index {idx} is not a land"
    return None


def exile_lands_for_sneak(
    zones: ZoneManager,
    player_idx: int,
    land_hand_indices: list[int],
) -> None:
    """Exile chosen lands from hand for sneak (call only after sneak_land_error passes)."""
    hand = zones.player_zones[player_idx].hand
    to_exile = [hand[idx] for idx in land_hand_indices]
    for card in to_exile:
        assert isinstance(card, CardObject)
        hand.remove(card)
        zones.player_zones[player_idx].exile.append(card)


def resolve_sneak_for_cast(
    card: CardInfo,
    mana_needed: int,
    zones: ZoneManager,
    player_idx: int,
    sneak: SneakCastInput,
) -> tuple[int, int, str | None]:
    """Apply sneak: validate, exile lands, return remaining mana and lands exiled."""
    raw_land_hand_indices = list(sneak.land_hand_indices)
    if raw_land_hand_indices and not has_sneak(card):
        return mana_needed, 0, f"{card.name} does not have sneak"
    sneak_indices = normalize_sneak_land_hand_indices(
        card,
        sneak.spell_hand_idx,
        raw_land_hand_indices,
    )
    if not sneak_indices:
        return mana_needed, 0, None
    max_lands = (mana_needed + SNEAK_MANA_PER_LAND - 1) // SNEAK_MANA_PER_LAND
    capped = sneak_indices[:max_lands] if max_lands < len(sneak_indices) else sneak_indices
    err = sneak_land_error(zones, player_idx, sneak.spell_hand_idx, capped)
    if err is not None:
        return mana_needed, 0, err
    exile_lands_for_sneak(zones, player_idx, capped)
    reduction = len(capped) * SNEAK_MANA_PER_LAND
    return max(0, mana_needed - reduction), len(capped), None
