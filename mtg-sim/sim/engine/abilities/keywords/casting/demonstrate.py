"""Demonstrate: copy the spell when cast (CR 702.143, simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_demonstrate(card: CardInfo) -> bool:
    """Return True when the spell has demonstrate."""
    if card.is_creature or card.is_land:
        return False
    return has_registered_keyword(card.oracle_text, 'Demonstrate')


def normalize_paid_demonstrate(card: CardInfo, paid_demonstrate: bool) -> bool:
    """Return whether this cast pays demonstrate."""
    return paid_demonstrate and has_demonstrate(card)


def supports_demonstrate_copies(card: CardInfo) -> bool:
    """Return True when a demonstrate copy is modeled for this spell."""
    return has_demonstrate(card) and not card.is_creature
