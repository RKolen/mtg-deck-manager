"""Gravestorm: copy the spell for each permanent that died this turn (CR 702.68)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_gravestorm(card: CardInfo) -> bool:
    """Return True when the card has gravestorm."""
    return has_registered_keyword(card.oracle_text, 'Gravestorm')


def gravestorm_copy_count(permanents_died_this_turn: int) -> int:
    """Return how many gravestorm copies to put on the stack."""
    return max(0, permanents_died_this_turn)


def supports_gravestorm_copies(card: CardInfo) -> bool:
    """Return True when gravestorm copies are modeled for this spell type."""
    return has_gravestorm(card) and not card.is_creature
