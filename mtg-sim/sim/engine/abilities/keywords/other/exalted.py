"""Exalted: alone attacking, this creature gets +1/+1 until end of turn (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_exalted(perm: Permanent) -> bool:
    """Return True when the permanent has exalted."""
    return has_keyword(perm, 'Exalted')


def apply_exalted_on_attack(
    game: GameState,
    attacker: Permanent,
    *,
    solo_attack: bool,
) -> str | None:
    """Grant +1/+1 when this is the only attacker (simplified exalted)."""
    del game
    if not solo_attack or not has_exalted(attacker):
        return None
    put_plus_counters(attacker, 1)
    return f"exalted +1/+1 on {attacker.name}"
