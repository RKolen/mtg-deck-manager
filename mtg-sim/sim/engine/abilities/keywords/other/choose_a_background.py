"""Choose a Background: partner variant with a Background commander (CR 702.124k)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_choose_a_background(card: CardInfo) -> bool:
    """Return True when the card has choose a background."""
    return has_registered_keyword(card.oracle_text, 'Choose a background')


def is_background(card: CardInfo) -> bool:
    """Return True when the card is a legendary Background enchantment."""
    type_line = card.type_line or ''
    return (
        'Enchantment' in type_line
        and 'Background' in type_line
        and 'Legendary' in type_line
    )


def find_choose_a_background_commander(deck: list[CardInfo]) -> CardInfo | None:
    """Return the choose-a-background commander in a deck, if any."""
    for card in deck:
        if has_choose_a_background(card):
            return card
    return None


def validate_choose_a_background_deck(deck: list[CardInfo]) -> str | None:
    """Return an error when background commander requirements are not met."""
    commander = find_choose_a_background_commander(deck)
    if commander is None:
        return None
    backgrounds = [card for card in deck if is_background(card)]
    if not backgrounds:
        return "Choose a Background deck must include a legendary Background"
    return None
