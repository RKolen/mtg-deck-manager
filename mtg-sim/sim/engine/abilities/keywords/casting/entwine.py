"""Entwine: pay an extra cost to choose all modes on a modal spell (CR 702.41)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.casting.kicker import spell_damage as kicker_spell_damage
from engine.cards.oracle_parse import parse_draw
from engine.core.mana import ManaCost

_ENTWINE_COST_RE = re.compile(
    r'entwine\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_ENTWINED_EXTRA_DAMAGE_RE = re.compile(
    r'if entwined.*?deals? (\d+) (?:more )?damage',
    re.IGNORECASE | re.DOTALL,
)
_CHOOSE_ONE_DRAW_RE = re.compile(
    r'•[^\n•]*draw',
    re.IGNORECASE,
)


def has_entwine(card: CardInfo) -> bool:
    """Return True when the card has entwine."""
    return has_registered_keyword(card.oracle_text, 'Entwine') or bool(
        _ENTWINE_COST_RE.search(card.oracle_text or '')
    )


def entwine_cost(card: CardInfo) -> ManaCost | None:
    """Parse the entwine additional cost from oracle text."""
    match = _ENTWINE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def entwine_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap when entwine is paid (simplified)."""
    cost = entwine_cost(card)
    return cost.mana_value if cost is not None else 0


def normalize_entwined(card: CardInfo, pay_entwine: bool) -> bool:
    """Return whether entwine is paid for this cast."""
    if not pay_entwine:
        return False
    return has_entwine(card)


def cast_mana_with_entwine(
    card: CardInfo,
    base_mana: int,
    life_cost: int,
    entwined: bool,
) -> tuple[int, int]:
    """Add entwine mana to a base cast cost when entwine is paid."""
    if normalize_entwined(card, entwined):
        return base_mana + entwine_mana_needed(card), life_cost
    return base_mana, life_cost


def resolve_burn_damage(card: CardInfo, entwined: bool, kicker_times: int = 0) -> int:
    """Resolve burn damage including entwined bonuses (MVP: base + optional extra)."""
    base = kicker_spell_damage(card, kicker_times)
    if not normalize_entwined(card, entwined):
        return base
    match = _ENTWINED_EXTRA_DAMAGE_RE.search(card.oracle_text or '')
    if match is not None:
        return base + int(match.group(1))
    if _CHOOSE_ONE_DRAW_RE.search(card.oracle_text or '') and base > 0:
        return base
    return base


def entwined_extra_draw(card: CardInfo, entwined: bool) -> int:
    """Return extra cards drawn when entwine selects an additional draw mode."""
    if not normalize_entwined(card, entwined):
        return 0
    if _CHOOSE_ONE_DRAW_RE.search(card.oracle_text or ''):
        return parse_draw(card.oracle_text or '') or 1
    return 0
