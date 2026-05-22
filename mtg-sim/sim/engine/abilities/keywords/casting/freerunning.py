"""Freerunning: alternate cost after your creature dealt combat damage (CR 702.172)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_FREERUNNING_COST_RE = re.compile(
    r'freerunning\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_freerunning(card: CardInfo) -> bool:
    """Return True when the card has freerunning."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Freerunning') or bool(
        _FREERUNNING_COST_RE.search(text)
    )


def freerunning_cost(card: CardInfo) -> ManaCost | None:
    """Parse the freerunning alternate cost from oracle text."""
    match = _FREERUNNING_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def freerunning_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the freerunning cost."""
    return alt_cost_mana_needed(freerunning_cost(card), card)


def normalize_freerunning_cast(
    card: CardInfo,
    cast_for_freerunning: bool,
    freerunning_available: bool,
) -> bool:
    """Return whether this cast uses the freerunning cost."""
    if not cast_for_freerunning or not freerunning_available:
        return False
    return has_freerunning(card)
