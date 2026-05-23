"""Embalm: create an exiled token copy (simplified)."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent, TokenObject
from engine.core.zones import ZoneManager


def has_embalm(perm: Permanent) -> bool:
    """Return True when the permanent has embalm."""
    return has_keyword(perm, 'Embalm')


def apply_embalm_etb(zones: ZoneManager, permanent: Permanent) -> str | None:
    """Create a white Zombie token in exile (simplified embalm)."""
    if not has_embalm(permanent):
        return None
    power, toughness = '4', '4'
    if permanent.card_info and permanent.card_info.pt:
        parts = permanent.card_info.pt.split('/')
        if len(parts) == 2:
            power, toughness = parts[0], parts[1]
    name = f"{permanent.name} Token"
    token = TokenObject(
        controller_idx=permanent.controller_idx,
        owner_idx=permanent.owner_idx,
        name=name,
        type_line='Creature — Zombie',
        colors=['W'],
        power=power,
        toughness=toughness,
        oracle_text='',
        created_by_obj_id=permanent.obj_id,
    )
    zones.player_zones[permanent.controller_idx].exile.append(token)
    return f"embalmed {name} (exile)"
