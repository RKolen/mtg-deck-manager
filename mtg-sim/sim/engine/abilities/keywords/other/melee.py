"""Melee: bonus when you attack with three or more creatures."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_MELEE_THRESHOLD = 3


def has_melee(perm: Permanent) -> bool:
    """Return True when the permanent has melee."""
    return has_keyword(perm, 'Melee')


def apply_melee_on_mass_attack(
    game: GameState,
    controller_idx: int,
    attacker_count: int,
) -> list[str]:
    """Apply melee bonuses when enough creatures attacked."""
    if attacker_count < _MELEE_THRESHOLD:
        return []
    details: list[str] = []
    for perm in game.zones.battlefield:
        if perm.controller_idx != controller_idx or not has_melee(perm):
            continue
        if 'draw a card' in (perm.oracle_text or '').lower():
            details.append(f"melee {perm.name} (draw)")
        else:
            details.append(f"melee {perm.name}")
    return details
