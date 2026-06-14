"""Fortify: equipment attaches to a land you control (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_fortify(perm: Permanent) -> bool:
    """Return True when the permanent has fortify."""
    return has_keyword(perm, 'Fortify')


def _first_land(battlefield: list[Permanent], controller_idx: int) -> Permanent | None:
    for perm in battlefield:
        if perm.controller_idx != controller_idx:
            continue
        if 'Land' in perm.type_line and 'Equipment' not in perm.type_line:
            return perm
    return None


def apply_fortify_etb(game: GameState, equipment: Permanent) -> str | None:
    """Attach fortify equipment to the first land its controller controls."""
    if not has_fortify(equipment) or 'Equipment' not in equipment.type_line:
        return None
    host = _first_land(game.zones.battlefield, equipment.controller_idx)
    if host is None:
        return f"fortify {equipment.name} (no land)"
    equipment.attached_to = host.obj_id
    return f"fortify {equipment.name} attached to {host.name}"
