"""Prowess: +1/+1 when you cast a noncreature spell (CR 702.109)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent


def has_prowess(perm: Permanent) -> bool:
    """Return True when the permanent has prowess."""
    return has_keyword(perm, 'Prowess')


def has_prowess_card(card: CardInfo) -> bool:
    """Return True when the card has prowess."""
    return has_registered_keyword(card.oracle_text, 'Prowess')
