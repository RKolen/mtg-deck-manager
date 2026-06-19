"""Phasing: permanents phase in and out on upkeep."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_phasing(perm: Permanent) -> bool:
    """Return True when the permanent has phasing."""
    return has_keyword(perm, 'Phasing')


def is_phased_out(perm: Permanent) -> bool:
    """Return True when the permanent is phased out."""
    return perm.phased_out


def resolve_phasing_upkeep(game: GameState, player_idx: int) -> list[str]:
    """Toggle phased status for each phasing permanent you control."""
    details: list[str] = []
    for perm in game.zones.battlefield:
        if perm.controller_idx != player_idx or not has_phasing(perm):
            continue
        perm.phased_out = not perm.phased_out
        state = 'out' if perm.phased_out else 'in'
        details.append(f"phasing {perm.name} ({state})")
    return details
