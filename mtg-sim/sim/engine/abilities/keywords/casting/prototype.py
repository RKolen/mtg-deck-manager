"""Prototype: cast for a lower cost as a smaller creature (simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost

_PROTOTYPE_RE = re.compile(
    r'prototype\s*((?:\{[^}]+\})+).*?(\d+)/(\d+)',
    re.IGNORECASE | re.DOTALL,
)


def has_prototype(card: CardInfo) -> bool:
    """Return True when the card has prototype."""
    if card.is_land:
        return False
    oracle = card.oracle_text or ''
    return has_registered_keyword(oracle, 'Prototype') or bool(
        _PROTOTYPE_RE.search(oracle)
    )


def prototype_cost(card: CardInfo) -> ManaCost | None:
    """Parse the prototype alternate cost from oracle text."""
    match = _PROTOTYPE_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def prototype_stats(card: CardInfo) -> tuple[int, int]:
    """Return prototype power and toughness."""
    match = _PROTOTYPE_RE.search(card.oracle_text or '')
    if match is None:
        return 0, 0
    return int(match.group(2)), int(match.group(3))


def prototype_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the prototype cost instead of the mana cost."""
    return alt_cost_mana_needed(prototype_cost(card), card)


def normalize_prototype_cast(card: CardInfo, cast_for_prototype: bool) -> bool:
    """Return whether this cast uses the prototype cost."""
    return cast_for_prototype and has_prototype(card)


def apply_prototype_on_etb(permanent: Permanent) -> str | None:
    """Set prototype P/T overrides when the creature entered for prototype."""
    card = permanent.card_info
    if card is None or not has_prototype(card):
        return None
    power, toughness = prototype_stats(card)
    if power <= 0 or toughness <= 0:
        return None
    permanent.counters['prototype_power'] = power
    permanent.counters['prototype_toughness'] = toughness
    return f"prototype {permanent.name} {power}/{toughness}"
