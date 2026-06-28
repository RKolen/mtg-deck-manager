"""Dash: alternate cost; haste and return to hand at end of turn (CR 702.110, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_DASH_COST_RE = re.compile(
    r'dash\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_dash(card: CardInfo) -> bool:
    """Return True when the creature may be cast for dash."""
    if not card.is_creature:
        return False
    return has_registered_keyword(card.oracle_text, 'Dash') or bool(
        _DASH_COST_RE.search(card.oracle_text or '')
    )


def has_dash_card(card: CardInfo) -> bool:
    """Return True when the card has dash."""
    return has_dash(card)


def dash_cost(card: CardInfo) -> ManaCost | None:
    """Parse the dash alternate cost from oracle text."""
    match = _DASH_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def dash_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the dash cost instead of the mana cost."""
    return alt_cost_mana_needed(dash_cost(card), card)


def normalize_dash_cast(card: CardInfo, cast_for_dash: bool) -> bool:
    """Return whether this cast uses the dash cost."""
    return cast_for_dash and has_dash(card)
