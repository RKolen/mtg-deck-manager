"""Exhaust: activated abilities may only be used once (simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

_EXHAUSTED_COUNTER = 'exhausted'


def has_exhaust(perm: Permanent) -> bool:
    """Return True when the permanent has exhaust on an activated ability."""
    return has_keyword(perm, 'Exhaust')


def has_exhaust_card(card: CardInfo) -> bool:
    """Return True when the card has exhaust."""
    return has_registered_keyword(card.oracle_text, 'Exhaust')


def can_use_exhaust_ability(perm: Permanent) -> bool:
    """Return True when an exhaust ability has not been used yet."""
    return has_exhaust(perm) and not perm.counters.get(_EXHAUSTED_COUNTER)


def mark_exhaust_used(perm: Permanent) -> str | None:
    """Mark exhaust as used for this permanent."""
    if not has_exhaust(perm):
        return None
    perm.counters[_EXHAUSTED_COUNTER] = 1
    return f"{perm.name} exhausted its ability"
