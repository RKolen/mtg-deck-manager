"""Escalate: pay extra mana for each target beyond the first (CR 702.119, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_ESCALATE_COST_RE = re.compile(
    r'escalate\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_escalate(card: CardInfo) -> bool:
    """Return True when the card has escalate."""
    return has_registered_keyword(card.oracle_text, 'Escalate') or bool(
        _ESCALATE_COST_RE.search(card.oracle_text or '')
    )


def has_escalate_card(card: CardInfo) -> bool:
    """Return True when the card has escalate."""
    return has_escalate(card)


def escalate_cost(card: CardInfo) -> ManaCost | None:
    """Parse the escalate cost from oracle text."""
    match = _ESCALATE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def escalate_mana_per_extra_target(card: CardInfo) -> int:
    """Return generic mana owed for each target beyond the first."""
    cost = escalate_cost(card)
    return cost.mana_value if cost is not None else 0


def normalize_escalate_extra_targets(card: CardInfo, extra_targets: int) -> int:
    """Clamp escalate target payments to legal values."""
    if extra_targets <= 0 or not has_escalate(card):
        return 0
    return extra_targets


def escalate_extra_mana(card: CardInfo, extra_targets: int) -> int:
    """Return additional generic mana owed for escalate targets."""
    times = normalize_escalate_extra_targets(card, extra_targets)
    return escalate_mana_per_extra_target(card) * times
