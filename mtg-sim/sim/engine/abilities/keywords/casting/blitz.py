"""Blitz: alternate cost; haste and sacrifice at end of turn (CR 702.154, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_BLITZ_COST_RE = re.compile(
    r'blitz\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_blitz(card: CardInfo) -> bool:
    """Return True when the creature may be cast for blitz."""
    if not card.is_creature:
        return False
    return has_registered_keyword(card.oracle_text, 'Blitz') or bool(
        _BLITZ_COST_RE.search(card.oracle_text or '')
    )


def has_blitz_card(card: CardInfo) -> bool:
    """Return True when the card has blitz."""
    return has_blitz(card)


def blitz_cost(card: CardInfo) -> ManaCost | None:
    """Parse the blitz alternate cost from oracle text."""
    match = _BLITZ_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def blitz_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the blitz cost instead of the mana cost."""
    return alt_cost_mana_needed(blitz_cost(card), card)


def normalize_blitz_cast(card: CardInfo, cast_for_blitz: bool) -> bool:
    """Return whether this cast uses the blitz cost."""
    return cast_for_blitz and has_blitz(card)
