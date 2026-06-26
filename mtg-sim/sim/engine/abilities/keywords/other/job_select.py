"""Job select: ETB creates a 1/1 Hero token and attaches equipment (CR 702.182)."""

from __future__ import annotations

from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent, TokenObject
from engine.core.zones import ZoneManager

_HERO_NAME = 'Hero'
_HERO_TYPE = 'Creature — Hero'


def has_job_select(perm: Permanent) -> bool:
    """Return True when the permanent has job select."""
    return has_registered_keyword(perm.oracle_text or '', 'Job select')


def apply_job_select(zones: ZoneManager, equipment: Permanent) -> str:
    """Create a Hero token and attach the equipment to it."""
    token = TokenObject(
        controller_idx=equipment.controller_idx,
        owner_idx=equipment.owner_idx,
        name=_HERO_NAME,
        type_line=_HERO_TYPE,
        colors=[],
        power='1',
        toughness='1',
        oracle_text='',
        created_by_obj_id=equipment.obj_id,
    )
    host = zones.enter_battlefield(token, equipment.controller_idx, 'job_select')
    equipment.attached_to = host.obj_id
    return f"job select created {host.name}"
