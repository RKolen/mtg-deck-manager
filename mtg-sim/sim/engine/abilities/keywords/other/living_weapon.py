"""Living weapon: ETB creates a 0/0 Germ token and attaches this equipment."""

from __future__ import annotations

from engine.abilities.keywords.registry import has_registered_keyword
from engine.cards.oracle_parse import TokenBlueprint
from engine.core.game_object import Permanent, TokenObject
from engine.core.zones import ZoneManager

_GERM = TokenBlueprint(
    name='Germ',
    type_line='Creature — Germ',
    power='0',
    toughness='0',
    colors=['B'],
    oracle_text='',
)


def has_living_weapon(oracle_text: str | None) -> bool:
    """Return True when the permanent has living weapon."""
    return has_registered_keyword(oracle_text, 'Living weapon')


def apply_living_weapon(zones: ZoneManager, equipment: Permanent) -> str:
    """Create a Germ token and attach the equipment to it."""
    token = TokenObject(
        controller_idx=equipment.controller_idx,
        owner_idx=equipment.owner_idx,
        name=_GERM.name,
        type_line=_GERM.type_line,
        colors=list(_GERM.colors),
        power=_GERM.power,
        toughness=_GERM.toughness,
        oracle_text=_GERM.oracle_text,
        created_by_obj_id=equipment.obj_id,
    )
    host = zones.enter_battlefield(token, equipment.controller_idx, 'living_weapon')
    equipment.attached_to = host.obj_id
    return f"Living weapon created {host.name}"
