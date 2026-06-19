"""Living metal: artifact is a 3/3 creature during combat (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_LIVING_METAL = 'living_metal'
_LIVING_METAL_BONUS = 3


def has_living_metal(perm: Permanent) -> bool:
    """Return True when the permanent has living metal."""
    return has_keyword(perm, 'Living metal')


def is_living_metal_creature(perm: Permanent) -> bool:
    """Return True when living metal is active on this permanent."""
    return perm.counters.get(_LIVING_METAL, 0) > 0


def activate_living_metal_for_combat(game: GameState, player_idx: int) -> list[str]:
    """Animate living metal artifacts as 3/3 creatures for combat."""
    details: list[str] = []
    for perm in game.zones.battlefield:
        if perm.controller_idx != player_idx or not has_living_metal(perm):
            continue
        if 'Artifact' not in perm.type_line or is_living_metal_creature(perm):
            continue
        perm.counters[_LIVING_METAL] = 1
        perm.counters['+1/+1'] = perm.counters.get('+1/+1', 0) + _LIVING_METAL_BONUS
        details.append(f"living metal {perm.name} 3/3")
    return details


def deactivate_living_metal_after_combat(game: GameState, player_idx: int) -> list[str]:
    """Remove living metal combat bonuses after combat."""
    details: list[str] = []
    for perm in game.zones.battlefield:
        if perm.controller_idx != player_idx or not perm.counters.pop(_LIVING_METAL, 0):
            continue
        perm.counters['+1/+1'] = max(0, perm.counters.get('+1/+1', 0) - _LIVING_METAL_BONUS)
        details.append(f"living metal {perm.name} deactivated")
    return details
