"""Bloodrush: discard a creature card from hand for a pump effect (ability word)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.activated._cost_keyword import (
    alt_cost_mana_value,
    discard_from_hand,
    timing_allows_hand_activation,
)
from engine.abilities.keywords.ability_words.detect import has_ability_word
from engine.abilities.keywords.actions.counters import put_power_bonus
from engine.abilities.keywords.actions.targets import find_creature_by_uid
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager
from engine.core.zone_card_lookup import hand_card_with_info

_BLOODRUSH_COST_RE = re.compile(
    r'bloodrush\s*[—–-]\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_bloodrush(card: CardInfo) -> bool:
    """Return True when the card has the Bloodrush ability word."""
    return card.is_creature and has_ability_word(card.oracle_text, 'Bloodrush')


def bloodrush_cost(card: CardInfo) -> ManaCost | None:
    """Parse the mana cost from a Bloodrush line."""
    match = _BLOODRUSH_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def bloodrush_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for bloodrush."""
    if bloodrush_cost(card) is None:
        return 0
    return alt_cost_mana_value(card, _BLOODRUSH_COST_RE)


def can_bloodrush(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when bloodrush may be used from hand."""
    return has_bloodrush(card) and timing_allows_hand_activation(
        phase,
        stack_is_empty,
    )


def bloodrush_power(card: CardInfo) -> int:
    """Return the power granted by this card's bloodrush."""
    if not card.pt or '/' not in card.pt:
        return 0
    left = card.pt.split('/', 1)[0].strip()
    return int(left) if left.isdigit() else 0


def apply_bloodrush(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
    target_creature_uid: str | None,
) -> str | None:
    """Discard the bloodrush card and grant +X/+0 to a target creature."""
    loaded = hand_card_with_info(zones, player_idx, hand_idx)
    if loaded is None:
        return None
    _card, card_info = loaded
    if not has_bloodrush(card_info):
        return None
    target = find_creature_by_uid(zones, target_creature_uid)
    if target is None:
        return None
    power = bloodrush_power(card_info)
    discard_from_hand(zones, player_idx, hand_idx)
    put_power_bonus(target, power)
    name = card_info.name
    return f"bloodrush {name}: +{power}/+0 on {target.name}"
