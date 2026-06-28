"""Evoke: cast for an alternate cost and sacrifice on ETB (CR 702.74)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_EVOKE_COST_RE = re.compile(
    r'evoke\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_evoke(card: CardInfo) -> bool:
    """Return True when the creature may be cast for its evoke cost."""
    if not card.is_creature:
        return False
    return has_registered_keyword(card.oracle_text, 'Evoke') or bool(
        _EVOKE_COST_RE.search(card.oracle_text or '')
    )


def has_evoke_card(card: CardInfo) -> bool:
    """Return True when the card has evoke."""
    return has_evoke(card)


def evoke_cost(card: CardInfo) -> ManaCost | None:
    """Parse the evoke alternate cost from oracle text."""
    match = _EVOKE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def evoke_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the evoke cost instead of the mana cost."""
    return alt_cost_mana_needed(evoke_cost(card), card)


def normalize_evoke_cast(card: CardInfo, cast_for_evoke: bool) -> bool:
    """Return whether this cast uses evoke."""
    return cast_for_evoke and has_evoke(card)
