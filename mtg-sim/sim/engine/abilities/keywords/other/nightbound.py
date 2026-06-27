"""Nightbound: enters on back face; toggles with daybound at upkeep."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords.other.daybound import (
    apply_nightbound_etb as _apply_nightbound_etb,
    has_nightbound as _has_nightbound_perm,
    is_daybound_front,
    resolve_daybound_upkeep,
)
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

apply_nightbound_etb = _apply_nightbound_etb


def has_nightbound(perm: Permanent) -> bool:
    """Return True when the permanent has nightbound."""
    return _has_nightbound_perm(perm)


def has_nightbound_card(card: CardInfo) -> bool:
    """Return True when the card has nightbound."""
    return has_registered_keyword(card.oracle_text, 'Nightbound')


def resolve_nightbound_upkeep(game: GameState, player_idx: int) -> list[str]:
    """Toggle nightbound permanents at upkeep (shared with daybound)."""
    return resolve_daybound_upkeep(game, player_idx)


__all__ = [
    'apply_nightbound_etb',
    'has_nightbound',
    'has_nightbound_card',
    'is_daybound_front',
    'resolve_nightbound_upkeep',
]
