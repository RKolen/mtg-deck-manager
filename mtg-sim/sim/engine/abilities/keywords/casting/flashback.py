"""Flashback: cast from graveyard for an alternate cost; exile on resolution."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_FLASHBACK_COST_RE = re.compile(
    r'flashback\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_INSTANT_SPEED_PHASES = frozenset({
    'main1',
    'main2',
    'attack',
    'declare_blockers',
})


def has_flashback(card: CardInfo) -> bool:
    """Return True when the card may be cast for its flashback cost."""
    return has_registered_keyword(card.oracle_text, 'Flashback') or bool(
        _FLASHBACK_COST_RE.search(card.oracle_text or '')
    )


def flashback_cost(card: CardInfo) -> ManaCost | None:
    """Parse the flashback alternate cost from oracle text."""
    match = _FLASHBACK_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def flashback_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for a flashback cast (simplified payment)."""
    cost = flashback_cost(card)
    if cost is None:
        return max(0, int(card.cmc) if card.cmc == int(card.cmc) else int(card.cmc))
    return cost.mana_value


def can_cast_via_flashback(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when flashback may be cast in the current timing window.

    Flashback may be cast any time its controller could cast an instant (CR 702.33a).
    """
    if card.is_land or not has_flashback(card):
        return False
    if phase in _INSTANT_SPEED_PHASES:
        return True
    return phase in ('main1', 'main2') and stack_is_empty
