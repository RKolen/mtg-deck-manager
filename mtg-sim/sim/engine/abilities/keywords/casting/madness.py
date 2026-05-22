"""Madness: cast for an alternate cost when discarding (CR 702.34, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_MADNESS_COST_RE = re.compile(
    r'madness\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
INSTANT_SPEED_PHASES = frozenset({
    'main1',
    'main2',
    'attack',
    'declare_blockers',
})


def has_madness(card: CardInfo) -> bool:
    """Return True when the card has madness."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Madness') or bool(
        _MADNESS_COST_RE.search(text)
    )


def madness_cost(card: CardInfo) -> ManaCost | None:
    """Parse the madness alternate cost from oracle text."""
    match = _MADNESS_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def madness_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the madness cost."""
    return alt_cost_mana_needed(madness_cost(card), card)


def can_cast_via_madness(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when madness may be cast in the current timing window."""
    if card.is_land or not has_madness(card):
        return False
    if phase in INSTANT_SPEED_PHASES:
        return True
    return phase in ('main1', 'main2') and stack_is_empty
