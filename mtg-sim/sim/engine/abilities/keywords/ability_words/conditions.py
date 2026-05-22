"""Trigger conditions for wired ability words."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.core.game_object import Permanent
from engine.core.zones import Zone, ZoneMoveEvent
from engine.rules.triggers import (
    CombatDamageTriggerEvent,
    SpellCastTriggerEvent,
    StepTriggerEvent,
    TriggerDefinition,
    TriggerEvent,
)
from engine.core.turn_structure import Step

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def is_controller_land_enters(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Landfall: a land entered the battlefield under your control."""
    return (
        isinstance(event, ZoneMoveEvent)
        and event.to_zone == Zone.BATTLEFIELD
        and isinstance(event.obj, Permanent)
        and 'Land' in event.obj.type_line
        and event.player_idx == definition.controller_idx
    )


def is_controller_enchantment_enters(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Constellation: an enchantment entered under your control."""
    return (
        isinstance(event, ZoneMoveEvent)
        and event.to_zone == Zone.BATTLEFIELD
        and isinstance(event.obj, Permanent)
        and 'Enchantment' in event.obj.type_line
        and event.player_idx == definition.controller_idx
    )


def is_raid_at_beginning_of_combat(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Raid: beginning of combat if an opponent was dealt damage this turn."""
    opponent = 1 - definition.controller_idx
    return (
        isinstance(event, StepTriggerEvent)
        and event.step == Step.BEGIN_COMBAT
        and event.active_player_idx == definition.controller_idx
        and game.players[opponent].was_dealt_damage_this_turn
    )


def is_controller_instant_or_sorcery_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Magecraft: you cast an instant or sorcery spell."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and (
            'Instant' in event.type_line
            or 'Sorcery' in event.type_line
        )
    )


def is_source_enraged(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Enrage: this creature was dealt damage."""
    return (
        isinstance(event, CombatDamageTriggerEvent)
        and event.damaged_permanent_id == definition.source_permanent_id
        and event.amount > 0
    )
