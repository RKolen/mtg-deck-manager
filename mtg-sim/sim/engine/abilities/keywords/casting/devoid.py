"""Devoid: spell is colorless even when its mana cost contains colored symbols (CR 702.38)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_devoid(card: CardInfo) -> bool:
    """Return True when the card has devoid."""
    return has_registered_keyword(card.oracle_text, 'Devoid')


def has_devoid_card(card: CardInfo) -> bool:
    """Return True when the card has devoid."""
    return has_devoid(card)


def spell_is_colorless_for_effects(card: CardInfo) -> bool:
    """Return True when color-matching effects should treat the spell as colorless."""
    return has_devoid(card)
