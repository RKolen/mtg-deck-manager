"""Soulbond: pair with another creature you control on ETB (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_SOULBOND_COUNTER = 'soulbond'


def has_soulbond(perm: Permanent) -> bool:
    """Return True when the permanent has soulbond."""
    return has_keyword(perm, 'Soulbond')


def soulbond_partner_id(perm: Permanent) -> int | None:
    """Return the obj_id of this permanent's soulbond partner, if any."""
    partner_id = perm.counters.get(_SOULBOND_COUNTER)
    return int(partner_id) if partner_id else None


def apply_soulbond_etb(game: GameState, permanent: Permanent) -> str | None:
    """Pair with another unpaired creature you control."""
    if not has_soulbond(permanent):
        return None
    if soulbond_partner_id(permanent) is not None:
        return None
    for perm in game.zones.battlefield:
        if perm.obj_id == permanent.obj_id:
            continue
        if perm.controller_idx != permanent.controller_idx:
            continue
        if 'Creature' not in perm.type_line or not has_soulbond(perm):
            continue
        if soulbond_partner_id(perm) is not None:
            continue
        permanent.counters[_SOULBOND_COUNTER] = perm.obj_id
        perm.counters[_SOULBOND_COUNTER] = permanent.obj_id
        return f"soulbond {permanent.name} + {perm.name}"
    return f"soulbond {permanent.name} (unpaired)"
