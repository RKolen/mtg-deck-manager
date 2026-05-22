"""Miracle: cast for a reduced cost when revealed on draw (CR 702.139, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_MIRACLE_COST_RE = re.compile(
    r'miracle\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_miracle(card: CardInfo) -> bool:
    """Return True when the card has miracle."""
    return has_registered_keyword(card.oracle_text, 'Miracle') or bool(
        _MIRACLE_COST_RE.search(card.oracle_text or '')
    )


def miracle_cost(card: CardInfo) -> ManaCost | None:
    """Parse the miracle alternate cost from oracle text."""
    match = _MIRACLE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def miracle_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the miracle cost instead of the mana cost."""
    return alt_cost_mana_needed(miracle_cost(card), card)


def normalize_miracle_cast(card: CardInfo, cast_for_miracle: bool) -> bool:
    """Return whether this cast uses the miracle cost."""
    if not cast_for_miracle:
        return False
    return has_miracle(card)
