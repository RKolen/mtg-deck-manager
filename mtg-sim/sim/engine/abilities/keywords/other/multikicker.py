"""Multikicker: kicker that may be paid multiple times (CR 702.96)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.casting.kicker import is_multikicker as _is_multikicker


def has_multikicker(card: CardInfo) -> bool:
    """Return True when the card has multikicker."""
    return _is_multikicker(card)
