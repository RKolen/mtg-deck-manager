"""Increment: +1/+1 counter when you cast a spell for enough mana (CR 702.191)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword, is_creature
from engine.core.game_object import Permanent, effective_power, effective_toughness

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_INCREMENT_COUNTER = '+1/+1'


def has_increment(perm: Permanent) -> bool:
    """Return True when the permanent has increment."""
    return has_keyword(perm, 'Increment')


def _creature_stats(perm: Permanent) -> tuple[int, int]:
    return effective_power(perm), effective_toughness(perm)


def increment_triggers(perm: Permanent, mana_spent: int) -> bool:
    """Return True when mana spent exceeds power or toughness."""
    if not is_creature(perm):
        return False
    power, toughness = _creature_stats(perm)
    return mana_spent > power or mana_spent > toughness


def apply_increment_on_spell_cast(
    game: GameState,
    controller_idx: int,
    card: CardInfo | None,
    *,
    mana_spent: int = 0,
) -> list[str]:
    """Put a +1/+1 counter on increment creatures when mana spent is high enough."""
    if card is None or mana_spent <= 0:
        return []
    details: list[str] = []
    for perm in game.zones.battlefield:
        if perm.controller_idx != controller_idx or not has_increment(perm):
            continue
        if not increment_triggers(perm, mana_spent):
            continue
        perm.counters[_INCREMENT_COUNTER] = perm.counters.get(_INCREMENT_COUNTER, 0) + 1
        details.append(f"increment {perm.name} (+1/+1)")
    return details


def parse_increment_reminder(oracle_text: str) -> bool:
    """Return True when oracle text mentions increment."""
    return bool(re.search(r'\bincrement\b', oracle_text or '', re.IGNORECASE))
