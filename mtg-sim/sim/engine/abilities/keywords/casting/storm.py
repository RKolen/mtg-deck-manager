"""Storm: copy the spell for each other spell cast this turn (CR 702.40)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_storm(card: CardInfo) -> bool:
    """Return True when the card has the storm keyword."""
    return has_registered_keyword(card.oracle_text, 'Storm')


def storm_copy_count(spells_cast_including_this: int) -> int:
    """Return how many storm copies to put on the stack.

    Count is taken after incrementing spells_cast_this_turn for this cast, so
    copies = other spells cast earlier this turn = total - 1.
    """
    return max(0, spells_cast_including_this - 1)


def supports_storm_copies(card: CardInfo) -> bool:
    """Return True when storm copies are modeled for this spell type.

    Noncreature spells share one source card across copies. Creature storm
    needs separate objects per copy and is not modeled yet.
    """
    return has_storm(card) and not card.is_creature
