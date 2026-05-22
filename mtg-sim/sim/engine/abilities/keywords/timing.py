"""Timing keywords: Haste, Flash."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword

if TYPE_CHECKING:
    from deck_registry import CardInfo
    from engine.core.game_object import Permanent


def enters_ready(perm: Permanent) -> bool:
    """Return True when a creature should not have summoning sickness on ETB."""
    return has_keyword(perm, 'Haste')


def has_flash(card: CardInfo) -> bool:
    """Return True when a spell may be cast at instant speed via Flash."""
    return (
        has_registered_keyword(card.oracle_text or '', 'Flash')
        or 'Instant' in card.type_line
    )
