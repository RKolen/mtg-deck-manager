"""Convoke: tap creatures you control to help pay generic mana (CR 702.124, simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.zones import ZoneManager


def has_convoke(card: CardInfo) -> bool:
    """Return True when the card has convoke."""
    return has_registered_keyword(card.oracle_text, 'Convoke')


def normalize_convoke_creature_ids(
    card: CardInfo,
    creature_ids: list[int],
) -> list[int]:
    """Return deduped creature ids when convoke applies; otherwise []."""
    if not creature_ids or not has_convoke(card):
        return []
    seen: set[int] = set()
    unique: list[int] = []
    for obj_id in creature_ids:
        if obj_id not in seen:
            seen.add(obj_id)
            unique.append(obj_id)
    return unique


def convoke_tap_error(
    zones: ZoneManager,
    player_idx: int,
    creature_ids: list[int],
) -> str | None:
    """Return an error message when convoke taps are illegal."""
    for obj_id in creature_ids:
        perm = zones.find_permanent(obj_id)
        if perm is None:
            return f"Convoke creature {obj_id} not found"
        if perm.controller_idx != player_idx:
            return "Convoke may only tap creatures you control"
        if perm.tapped:
            return f"{perm.name} is already tapped"
        if "Creature" not in perm.type_line:
            return f"{perm.name} is not a creature"
    return None


def tap_convoke_creatures(zones: ZoneManager, creature_ids: list[int]) -> None:
    """Tap permanents chosen for convoke (call only after convoke_tap_error passes)."""
    for obj_id in creature_ids:
        perm = zones.find_permanent(obj_id)
        assert perm is not None
        perm.tapped = True


def resolve_convoke_for_cast(
    card: CardInfo,
    mana_needed: int,
    raw_creature_ids: list[int],
    zones: ZoneManager,
    player_idx: int,
) -> tuple[int, list[int], str | None]:
    """Apply convoke: validate, tap creatures, return remaining land mana and ids."""
    if raw_creature_ids and not has_convoke(card):
        return mana_needed, [], f"{card.name} does not have convoke"
    convoke_ids = normalize_convoke_creature_ids(card, raw_creature_ids)
    if not convoke_ids:
        return mana_needed, [], None
    capped = convoke_ids[:mana_needed] if mana_needed < len(convoke_ids) else convoke_ids
    err = convoke_tap_error(zones, player_idx, capped)
    if err is not None:
        return mana_needed, [], err
    tap_convoke_creatures(zones, capped)
    return max(0, mana_needed - len(capped)), capped, None
