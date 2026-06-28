"""Typecycling activated abilities (Forestcycling, Wizardcycling, etc.)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.activated.card_keyword_abilities import (
    cycling_cost,
    cycling_mana_needed,
)
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_TYPECYCLING_KEYWORDS: tuple[tuple[str, str], ...] = (
    ('Basic landcycling', 'Basic Land'),
    ('Forestcycling', 'Forest'),
    ('Islandcycling', 'Island'),
    ('Landcycling', 'Land'),
    ('Mountaincycling', 'Mountain'),
    ('Plainscycling', 'Plains'),
    ('Slivercycling', 'Sliver'),
    ('Swampcycling', 'Swamp'),
    ('Typecycling', 'Type'),
    ('Wizardcycling', 'Wizard'),
)


def _has_typecycling_keyword(card: CardInfo, keyword: str) -> bool:
    return has_registered_keyword(card.oracle_text, keyword)


def has_forestcycling_card(card: CardInfo) -> bool:
    """Return True when the card has forestcycling."""
    return _has_typecycling_keyword(card, 'Forestcycling')


def has_islandcycling_card(card: CardInfo) -> bool:
    """Return True when the card has islandcycling."""
    return _has_typecycling_keyword(card, 'Islandcycling')


def has_swampcycling_card(card: CardInfo) -> bool:
    """Return True when the card has swampcycling."""
    return _has_typecycling_keyword(card, 'Swampcycling')


def has_mountaincycling_card(card: CardInfo) -> bool:
    """Return True when the card has mountaincycling."""
    return _has_typecycling_keyword(card, 'Mountaincycling')


def has_plainscycling_card(card: CardInfo) -> bool:
    """Return True when the card has plainscycling."""
    return _has_typecycling_keyword(card, 'Plainscycling')


def has_wizardcycling_card(card: CardInfo) -> bool:
    """Return True when the card has wizardcycling."""
    return _has_typecycling_keyword(card, 'Wizardcycling')


def has_typecycling_card(card: CardInfo) -> bool:
    """Return True when the card has any typecycling variant."""
    return typecycling_discard_requirement(card) is not None


def typecycling_discard_requirement(card: CardInfo) -> str | None:
    """Return the land or creature type to discard, if any."""
    for keyword, requirement in _TYPECYCLING_KEYWORDS:
        if _has_typecycling_keyword(card, keyword):
            return requirement
    return None


def typecycling_cost(card: CardInfo) -> ManaCost | None:
    """Parse the typecycling mana cost (same pattern as cycling)."""
    return cycling_cost(card)


def typecycling_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for a typecycling activation."""
    return cycling_mana_needed(card)
