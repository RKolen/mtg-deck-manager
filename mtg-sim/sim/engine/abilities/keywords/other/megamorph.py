"""Megamorph: morph variant that adds a +1/+1 counter when turned face up."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.other.morph import (
    apply_turn_up_morph,
    has_megamorph as _has_megamorph,
    morph_turn_up_cost,
    morph_turn_up_mana_needed,
)
from engine.core.game_object import Permanent
from engine.core.game_state import GameState

has_megamorph = _has_megamorph


def has_megamorph_card(card: CardInfo) -> bool:
    """Return True when the card has megamorph."""
    return has_megamorph(card)


def megamorph_turn_up_mana_needed(card: CardInfo) -> int:
    """Return generic mana to turn a megamorph creature face up."""
    if not has_megamorph(card):
        return 0
    return morph_turn_up_mana_needed(card)


def apply_megamorph_turn_up(_game: GameState, permanent: Permanent) -> str | None:
    """Turn a megamorph creature face up and add its +1/+1 counter."""
    if permanent.card_info is None or not has_megamorph(permanent.card_info):
        return None
    return apply_turn_up_morph(permanent)


__all__ = [
    'apply_megamorph_turn_up',
    'has_megamorph',
    'has_megamorph_card',
    'megamorph_turn_up_mana_needed',
    'morph_turn_up_cost',
]
