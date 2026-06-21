"""Compleated: pay life instead of colored mana when casting (simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword

_COMPLEATED_RE = re.compile(r'compleated', re.IGNORECASE)
_COLORED_SYMBOL = re.compile(r'\{([WUBRG])\}')


def has_compleated(card: CardInfo) -> bool:
    """Return True when the card has compleated."""
    return has_registered_keyword(card.oracle_text, 'Compleated') or bool(
        _COMPLEATED_RE.search(card.oracle_text or '')
    )


def compleated_life_extra(card: CardInfo, paid_compleated: bool) -> int:
    """Return extra life owed when casting compleated (2 per colored pip)."""
    if not paid_compleated or not has_compleated(card):
        return 0
    mana_cost = card.mana_cost or ''
    colored = len(_COLORED_SYMBOL.findall(mana_cost))
    return colored * 2


def normalize_paid_compleated(card: CardInfo, paid_compleated: bool) -> bool:
    """Return whether compleated was paid."""
    return paid_compleated and has_compleated(card)
