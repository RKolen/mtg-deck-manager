"""Friends forever: partner variant requiring two friends-forever commanders."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_friends_forever(card: CardInfo) -> bool:
    """Return True when the card has friends forever."""
    return has_registered_keyword(card.oracle_text, 'Friends forever')


def validate_friends_forever_deck(deck: list[CardInfo]) -> str | None:
    """Return an error when friends forever deck requirements are not met."""
    friends = [card for card in deck if has_friends_forever(card)]
    if not friends:
        return None
    if len(friends) < 2:
        return "Friends forever deck must include two friends forever commanders"
    return None
