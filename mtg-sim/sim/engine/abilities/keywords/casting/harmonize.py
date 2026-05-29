"""Harmonize: cast from graveyard for harmonize cost; optional creature tap reduces generic."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting._timing import INSTANT_SPEED_PHASES
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager
from engine.core.game_object import effective_power

_HARMONIZE_COST_RE = re.compile(
    r'harmonize\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_harmonize(card: CardInfo) -> bool:
    """Return True when the card may be cast for its harmonize cost."""
    return has_registered_keyword(card.oracle_text, 'Harmonize') or bool(
        _HARMONIZE_COST_RE.search(card.oracle_text or '')
    )


def harmonize_cost(card: CardInfo) -> ManaCost | None:
    """Parse the harmonize alternate cost from oracle text."""
    match = _HARMONIZE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def harmonize_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return base mana and life to pay the harmonize cost."""
    return alt_cost_mana_needed(harmonize_cost(card), card)


def can_cast_via_harmonize(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when harmonize may be cast in the current timing window."""
    if card.is_land or not has_harmonize(card):
        return False
    if phase in INSTANT_SPEED_PHASES:
        return True
    return phase in ('main1', 'main2') and stack_is_empty


def normalize_harmonize_creature_id(
    card: CardInfo,
    creature_ids: list[int],
) -> int | None:
    """Return the creature id tapped for harmonize cost reduction, if any."""
    if not creature_ids or not has_harmonize(card):
        return None
    return creature_ids[0]


def harmonize_tap_error(
    zones: ZoneManager,
    player_idx: int,
    creature_id: int | None,
) -> str | None:
    """Return an error message when the harmonize tap is illegal."""
    if creature_id is None:
        return None
    perm = zones.find_permanent(creature_id)
    if perm is None:
        return f"Harmonize creature {creature_id} not found"
    if perm.controller_idx != player_idx:
        return "Harmonize may only tap creatures you control"
    if perm.tapped:
        return f"{perm.name} is already tapped"
    if 'Creature' not in perm.type_line:
        return f"{perm.name} is not a creature"
    return None


def tap_for_harmonize(zones: ZoneManager, creature_id: int) -> None:
    """Tap the creature chosen for harmonize (call only after harmonize_tap_error passes)."""
    perm = zones.find_permanent(creature_id)
    assert perm is not None
    perm.tapped = True


def harmonize_generic_reduction(perm: Permanent) -> int:
    """Return generic mana reduction from tapping this creature for harmonize."""
    return effective_power(perm)


def resolve_harmonize_mana(
    card: CardInfo,
    zones: ZoneManager,
    player_idx: int,
    creature_id: int | None,
) -> tuple[int, int, str | None]:
    """Apply optional harmonize tap and return remaining mana, life, and error."""
    mana_needed, life_cost = harmonize_mana_needed(card)
    if creature_id is None:
        return mana_needed, life_cost, None
    err = harmonize_tap_error(zones, player_idx, creature_id)
    if err is not None:
        return mana_needed, life_cost, err
    perm = zones.find_permanent(creature_id)
    assert perm is not None
    tap_for_harmonize(zones, creature_id)
    reduction = harmonize_generic_reduction(perm)
    return max(0, mana_needed - reduction), life_cost, None
