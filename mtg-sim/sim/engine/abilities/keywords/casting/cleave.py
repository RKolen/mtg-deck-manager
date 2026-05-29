"""Cleave: alternate cost to copy the spell with different targets (CR 702.139, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_CLEAVE_COST_RE = re.compile(
    r'cleave\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_cleave(card: CardInfo) -> bool:
    """Return True when the card has cleave."""
    return has_registered_keyword(card.oracle_text, 'Cleave') or bool(
        _CLEAVE_COST_RE.search(card.oracle_text or '')
    )


def cleave_cost(card: CardInfo) -> ManaCost | None:
    """Parse the cleave alternate cost from oracle text."""
    match = _CLEAVE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def cleave_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the cleave cost instead of the mana cost."""
    return alt_cost_mana_needed(cleave_cost(card), card)


def normalize_cleave_cast(card: CardInfo, pay_cleave: bool) -> bool:
    """Return whether cleave is paid for this cast."""
    if not pay_cleave:
        return False
    return has_cleave(card)


def supports_cleave_copies(card: CardInfo) -> bool:
    """Return True when a cleave copy is modeled for this spell."""
    return has_cleave(card) and not card.is_creature
