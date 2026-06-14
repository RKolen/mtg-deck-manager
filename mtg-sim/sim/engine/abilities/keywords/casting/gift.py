"""Gift: opponent receives a bonus when you pay gift (simplified: draw a card)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_gift(card: CardInfo) -> bool:
    """Return True when the spell has gift."""
    if card.is_land:
        return False
    return has_registered_keyword(card.oracle_text, 'Gift')


def normalize_paid_gift(card: CardInfo, paid_gift: bool) -> bool:
    """Return whether this cast pays gift."""
    return paid_gift and has_gift(card)


def gift_opponent_draws(card: CardInfo, paid_gift: bool) -> bool:
    """Return True when the opponent should draw from a paid gift."""
    return normalize_paid_gift(card, paid_gift)
