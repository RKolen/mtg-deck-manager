"""Overload: alternate cost to affect each opponent or each creature (CR 702.95)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.casting.kicker import spell_damage as kicker_spell_damage
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.core.mana import ManaCost
from engine.core.game_object import Permanent

_OVERLOAD_COST_RE = re.compile(
    r'overload\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_overload(card: CardInfo) -> bool:
    """Return True when the card has overload."""
    return has_registered_keyword(card.oracle_text, 'Overload') or bool(
        _OVERLOAD_COST_RE.search(card.oracle_text or '')
    )


def overload_cost(card: CardInfo) -> ManaCost | None:
    """Parse the overload alternate cost from oracle text."""
    match = _OVERLOAD_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def overload_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the overload cost instead of the mana cost."""
    return alt_cost_mana_needed(overload_cost(card), card)


def normalize_overloaded(card: CardInfo, pay_overload: bool) -> bool:
    """Return whether overload is paid for this cast."""
    if not pay_overload:
        return False
    return has_overload(card)


def overload_hits_each_creature(card: CardInfo) -> bool:
    """Return True when overloaded text affects each creature."""
    return 'each creature' in (card.oracle_text or '').lower()


def overload_opponent_indices(controller_idx: int, player_count: int = 2) -> list[int]:
    """Return player indices damaged when overload hits each opponent."""
    return [idx for idx in range(player_count) if idx != controller_idx]


def resolve_overload_burn_damage(
    card: CardInfo,
    kicker_times: int = 0,
) -> int:
    """Return damage dealt per overloaded target."""
    return kicker_spell_damage(card, kicker_times)


def overload_creature_targets(permanents: list[Permanent]) -> list[Permanent]:
    """Return creatures to damage when overload hits each creature."""
    return [p for p in permanents if 'Creature' in p.type_line]
