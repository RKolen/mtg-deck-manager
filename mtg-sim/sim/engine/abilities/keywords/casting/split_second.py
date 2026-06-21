"""Split second: spells with split second can't be countered (simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import SpellOnStack, StackObject


def has_split_second(card: CardInfo) -> bool:
    """Return True when the card has split second."""
    return has_registered_keyword(card.oracle_text, 'Split second')


def stack_object_has_split_second(obj: StackObject) -> bool:
    """Return True when a stack object can't be countered due to split second."""
    if isinstance(obj, SpellOnStack) and obj.casting.split_second:
        return True
    if isinstance(obj, SpellOnStack) and obj.source is not None:
        card = obj.source.card_info
        if card is not None and has_split_second(card):
            return True
    return False


def can_counter_stack_object(obj: StackObject) -> bool:
    """Return True when the top stack object may be countered."""
    return not stack_object_has_split_second(obj)
