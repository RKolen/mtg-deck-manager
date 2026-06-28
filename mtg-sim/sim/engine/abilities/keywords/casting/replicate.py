"""Replicate: pay the replicate cost any number of times for extra copies (CR 702.55)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_REPLICATE_COST_RE = re.compile(
    r'replicate\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_replicate(card: CardInfo) -> bool:
    """Return True when the card has replicate."""
    return has_registered_keyword(card.oracle_text, 'Replicate') or bool(
        _REPLICATE_COST_RE.search(card.oracle_text or '')
    )


def has_replicate_card(card: CardInfo) -> bool:
    """Return True when the card has replicate."""
    return has_replicate(card)


def replicate_cost(card: CardInfo) -> ManaCost | None:
    """Parse the replicate cost from oracle text."""
    match = _REPLICATE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def replicate_mana_per_time(card: CardInfo) -> int:
    """Return generic mana lands to tap for each replicate payment (simplified)."""
    cost = replicate_cost(card)
    return cost.mana_value if cost is not None else 0


def normalize_replicate_times(card: CardInfo, replicate_times: int) -> int:
    """Clamp replicate payments to legal values for this card."""
    if replicate_times <= 0 or not has_replicate(card):
        return 0
    return replicate_times


def replicate_extra_mana(card: CardInfo, replicate_times: int) -> int:
    """Return additional generic mana owed for replicate payments."""
    times = normalize_replicate_times(card, replicate_times)
    return replicate_mana_per_time(card) * times


def supports_replicate_copies(card: CardInfo) -> bool:
    """Return True when replicate copies are modeled for this spell type."""
    return has_replicate(card) and not card.is_creature
