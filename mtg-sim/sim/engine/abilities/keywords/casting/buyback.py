"""Buyback: optional additional cost; spell returns to hand on resolution (CR 702.21)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_BUYBACK_COST_RE = re.compile(
    r'buyback\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_buyback(card: CardInfo) -> bool:
    """Return True when the card has buyback."""
    return has_registered_keyword(card.oracle_text, 'Buyback') or bool(
        _BUYBACK_COST_RE.search(card.oracle_text or '')
    )


def has_buyback_card(card: CardInfo) -> bool:
    """Return True when the card has buyback."""
    return has_buyback(card)


def buyback_cost(card: CardInfo) -> ManaCost | None:
    """Parse the buyback cost from oracle text."""
    match = _BUYBACK_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def buyback_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for buyback (simplified payment)."""
    cost = buyback_cost(card)
    return cost.mana_value if cost is not None else 0


def normalize_buyback(card: CardInfo, paid_buyback: bool) -> bool:
    """Return True when buyback was legally paid for this card."""
    return paid_buyback and has_buyback(card)


def buyback_extra_mana(card: CardInfo, paid_buyback: bool) -> int:
    """Return additional generic mana owed when buyback is paid."""
    if not normalize_buyback(card, paid_buyback):
        return 0
    return buyback_mana_needed(card)
