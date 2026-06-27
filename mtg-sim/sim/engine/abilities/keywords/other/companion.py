"""Companion: deck-building restriction (simplified validation)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword

_COMPANION_RE = re.compile(
    r'companion\s*[—–-]\s*(.+?)(?:\n|$)',
    re.IGNORECASE,
)


def has_companion(card: CardInfo) -> bool:
    """Return True when the card is a companion."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Companion') or bool(_COMPANION_RE.search(text))


def has_companion_card(card: CardInfo) -> bool:
    """Return True when the card is a companion."""
    return has_companion(card)


def companion_restriction(card: CardInfo) -> str | None:
    """Return the companion deck-building rule text."""
    match = _COMPANION_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return match.group(1).strip()


def _deck_satisfies_restriction(restriction: str, deck: list[CardInfo]) -> bool:
    lowered = restriction.lower()
    if 'only cards with mana value' in lowered or 'mana value 3 or greater' in lowered:
        return all(card.cmc >= 3 or card.is_land for card in deck)
    if 'only permanents' in lowered:
        return all(
            card.is_land
            or 'Artifact' in card.type_line
            or 'Creature' in card.type_line
            or 'Enchantment' in card.type_line
            or 'Planeswalker' in card.type_line
            for card in deck
        )
    if 'only creature cards' in lowered:
        return all(card.is_creature or card.is_land for card in deck)
    return True


def find_companion_in_deck(deck: list[CardInfo]) -> CardInfo | None:
    """Return the companion card in a deck list, if any."""
    for card in deck:
        if has_companion(card):
            return card
    return None


def validate_companion_deck(deck: list[CardInfo]) -> str | None:
    """Return an error when the deck violates its companion restriction."""
    companion = find_companion_in_deck(deck)
    if companion is None:
        return None
    restriction = companion_restriction(companion)
    if restriction is None:
        return None
    if _deck_satisfies_restriction(restriction, deck):
        return None
    return f"Deck violates companion rule: {restriction}"
