"""Delve: exile cards from your graveyard to help pay generic mana (CR 702.56, simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.casting._indices import normalize_unique_indices
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager


def has_delve(card: CardInfo) -> bool:
    """Return True when the card has delve."""
    return has_registered_keyword(card.oracle_text, 'Delve')


def normalize_delve_graveyard_indices(
    card: CardInfo,
    graveyard_indices: list[int],
) -> list[int]:
    """Return deduped graveyard indices when delve applies; otherwise []."""
    if not graveyard_indices or not has_delve(card):
        return []
    return normalize_unique_indices(graveyard_indices)


def delve_exile_error(
    zones: ZoneManager,
    player_idx: int,
    graveyard_indices: list[int],
) -> str | None:
    """Return an error message when delve exiles are illegal."""
    graveyard = zones.player_zones[player_idx].graveyard
    for idx in graveyard_indices:
        if idx < 0 or idx >= len(graveyard):
            return f"Delve graveyard index {idx} out of range"
        card = graveyard[idx]
        if not isinstance(card, CardObject):
            return f"Delve index {idx} is not a card"
    return None


def exile_for_delve(
    zones: ZoneManager,
    player_idx: int,
    graveyard_indices: list[int],
) -> None:
    """Exile graveyard cards chosen for delve (call only after delve_exile_error passes)."""
    graveyard = zones.player_zones[player_idx].graveyard
    cards_to_exile = [
        graveyard[idx]
        for idx in graveyard_indices
    ]
    for card in cards_to_exile:
        assert isinstance(card, CardObject)
        zones.exile_from_graveyard(card, player_idx)


def resolve_delve_for_cast(
    card: CardInfo,
    mana_needed: int,
    raw_graveyard_indices: list[int],
    zones: ZoneManager,
    player_idx: int,
) -> tuple[int, int, str | None]:
    """Apply delve: validate, exile cards, return remaining land mana and count exiled."""
    if raw_graveyard_indices and not has_delve(card):
        return mana_needed, 0, f"{card.name} does not have delve"
    delve_indices = normalize_delve_graveyard_indices(card, raw_graveyard_indices)
    if not delve_indices:
        return mana_needed, 0, None
    capped = (
        delve_indices[:mana_needed]
        if mana_needed < len(delve_indices)
        else delve_indices
    )
    err = delve_exile_error(zones, player_idx, capped)
    if err is not None:
        return mana_needed, 0, err
    exile_for_delve(zones, player_idx, capped)
    return max(0, mana_needed - len(capped)), len(capped), None
