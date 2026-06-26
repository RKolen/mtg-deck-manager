"""Doctor's companion: partner variant with a Time Lord Doctor (simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_doctors_companion(card: CardInfo) -> bool:
    """Return True when the card has Doctor's companion."""
    return has_registered_keyword(card.oracle_text, "Doctor's companion")


def is_the_doctor(card: CardInfo) -> bool:
    """Return True when the card is a Time Lord Doctor with no other creature types."""
    type_line = card.type_line or ''
    if 'Legendary' not in type_line or 'Creature' not in type_line:
        return False
    if 'Time Lord Doctor' not in type_line:
        return False
    subtype_part = type_line.split('—', 1)[-1].strip().lower()
    tokens = [part.strip() for part in subtype_part.split() if part.strip()]
    return tokens == ['time', 'lord', 'doctor']


def find_doctors_companion(deck: list[CardInfo]) -> CardInfo | None:
    """Return a Doctor's companion card in the deck, if any."""
    for card in deck:
        if has_doctors_companion(card):
            return card
    return None


def validate_doctors_companion_deck(deck: list[CardInfo]) -> str | None:
    """Return an error when Doctor's companion requirements are not met."""
    companion = find_doctors_companion(deck)
    if companion is None:
        return None
    doctors = [card for card in deck if is_the_doctor(card)]
    if not doctors:
        return "Doctor's companion deck must include a Time Lord Doctor commander"
    return None
