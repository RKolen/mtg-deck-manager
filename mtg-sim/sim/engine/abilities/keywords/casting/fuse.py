"""Fuse: cast both halves of a split spell (CR 702.85, simplified copy)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_fuse(card: CardInfo) -> bool:
    """Return True when the card has fuse."""
    if card.is_land:
        return False
    return has_registered_keyword(card.oracle_text, 'Fuse')


def normalize_paid_fuse(card: CardInfo, paid_fuse: bool) -> bool:
    """Return whether this cast pays fuse."""
    return paid_fuse and has_fuse(card)


def supports_fuse_copies(card: CardInfo) -> bool:
    """Return True when a fuse copy is modeled for this spell."""
    return has_fuse(card) and not card.is_creature
