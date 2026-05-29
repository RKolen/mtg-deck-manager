"""Reusable trigger condition fragments."""

from __future__ import annotations

from engine.core.game_object import Permanent, effective_power
from engine.core.zones import Zone, ZoneMoveEvent
from engine.rules.triggers import TriggerDefinition, TriggerEvent


def is_controller_creature_enters_battlefield(
    event: TriggerEvent,
    definition: TriggerDefinition,
    *,
    exclude_source_id: int | None = None,
    min_power: int | None = None,
) -> bool:
    """True when a creature entered the battlefield under the controller."""
    if not (
        isinstance(event, ZoneMoveEvent)
        and event.to_zone == Zone.BATTLEFIELD
        and isinstance(event.obj, Permanent)
        and 'Creature' in event.obj.type_line
        and event.player_idx == definition.controller_idx
    ):
        return False
    if exclude_source_id is not None and event.obj.obj_id == exclude_source_id:
        return False
    if min_power is not None and effective_power(event.obj) < min_power:
        return False
    return True


def is_source_enters_battlefield(
    event: TriggerEvent,
    definition: TriggerDefinition,
) -> bool:
    """True when this permanent entered the battlefield."""
    return (
        isinstance(event, ZoneMoveEvent)
        and event.to_zone == Zone.BATTLEFIELD
        and isinstance(event.obj, Permanent)
        and event.obj.obj_id == definition.source_permanent_id
    )
