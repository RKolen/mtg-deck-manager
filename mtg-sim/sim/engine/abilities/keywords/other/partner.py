"""Partner: deck must include two partner commanders (simplified validation)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.other.partner_with import (
    has_partner_with,
    validate_partner_with_deck,
)
from engine.abilities.keywords.registry import has_registered_keyword


def has_partner(card: CardInfo) -> bool:
    """Return True when the card has partner or partner with."""
    text = card.oracle_text or ''
    if has_registered_keyword(text, 'Partner'):
        return True
    return has_partner_with(card)


def validate_partner_deck(deck: list[CardInfo]) -> str | None:
    """Return an error when partner deck requirements are not met."""
    partner_with_err = validate_partner_with_deck(deck)
    if partner_with_err is not None:
        return partner_with_err
    partners = [card for card in deck if has_partner(card)]
    if not partners:
        return None
    if len(partners) < 2:
        return "Partner deck must include two partner legendary creatures"
    return None
