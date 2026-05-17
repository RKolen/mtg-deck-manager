"""Triggered ability registration and firing helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from engine.core.game_object import Effect, Permanent, Target, TriggeredAbilityOnStack
from engine.core.turn_structure import Step
from engine.core.zones import Zone, ZoneMoveEvent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


class TriggerKey(StrEnum):
    """Known trigger timing/event keys."""

    ENTERS_BATTLEFIELD = "enters_battlefield"
    DIES = "dies"
    ATTACKS = "attacks"
    BEGINNING_OF_UPKEEP = "beginning_of_upkeep"


@dataclass(frozen=True)
class StepTriggerEvent:
    """Synthetic event for triggers that fire at the start of a turn step."""

    step: Step
    active_player_idx: int


@dataclass(frozen=True)
class AttackTriggerEvent:
    """Synthetic event emitted when an attacker is declared."""

    attacker_id: int
    attacking_player_idx: int


TriggerEvent = ZoneMoveEvent | StepTriggerEvent | AttackTriggerEvent
TriggerCondition = Callable[[TriggerEvent, "GameState"], bool]


@dataclass(frozen=True)
class TriggerDefinition:
    """A registered triggered ability on a permanent."""

    source_permanent_id: int
    controller_idx: int
    trigger_key: TriggerKey
    condition: TriggerCondition
    effect: Effect | None = None
    targets: tuple[Target, ...] = ()


@dataclass
class TriggerRegistry:
    """Registry of triggered abilities that can fire from game events."""

    _definitions: list[TriggerDefinition] = field(default_factory=list)

    def register(
        self,
        permanent: Permanent,
        trigger_key: TriggerKey,
        condition: TriggerCondition,
        effect: Effect | None = None,
        targets: tuple[Target, ...] = (),
    ) -> None:
        """Register a triggered ability controlled by a permanent."""
        self._definitions.append(
            TriggerDefinition(
                source_permanent_id=permanent.obj_id,
                controller_idx=permanent.controller_idx,
                trigger_key=trigger_key,
                condition=condition,
                effect=effect,
                targets=targets,
            )
        )

    def fire(
        self,
        event: TriggerEvent,
        game: GameState,
    ) -> list[TriggeredAbilityOnStack]:
        """Return triggered abilities that fire from the event."""
        return [
            _to_stack_object(definition)
            for definition in self._definitions
            if _source_can_trigger(definition, event, game)
            and definition.condition(event, game)
        ]

    def put_triggers_on_stack(
        self,
        event: TriggerEvent,
        game: GameState,
    ) -> list[TriggeredAbilityOnStack]:
        """Create triggered abilities and put them on the game stack."""
        abilities = self.fire(event, game)
        for ability in abilities:
            game.stack.push(ability)
        return abilities


def is_enters_battlefield(event: TriggerEvent, _game: GameState) -> bool:
    """Return True when an event moved an object onto the battlefield."""
    return isinstance(event, ZoneMoveEvent) and event.to_zone == Zone.BATTLEFIELD


def is_dies(event: TriggerEvent, _game: GameState) -> bool:
    """Return True when a creature moved from battlefield to graveyard."""
    return (
        isinstance(event, ZoneMoveEvent)
        and isinstance(event.obj, Permanent)
        and event.from_zone == Zone.BATTLEFIELD
        and event.to_zone == Zone.GRAVEYARD
        and "Creature" in event.obj.type_line
    )


def is_attacks(event: TriggerEvent, _game: GameState) -> bool:
    """Return True when an attacker is declared."""
    return isinstance(event, AttackTriggerEvent)


def is_beginning_of_upkeep(event: TriggerEvent, _game: GameState) -> bool:
    """Return True when upkeep begins."""
    return isinstance(event, StepTriggerEvent) and event.step == Step.UPKEEP


def _to_stack_object(definition: TriggerDefinition) -> TriggeredAbilityOnStack:
    return TriggeredAbilityOnStack(
        controller_idx=definition.controller_idx,
        owner_idx=definition.controller_idx,
        source_permanent_id=definition.source_permanent_id,
        trigger_key=definition.trigger_key.value,
        effect=definition.effect,
        targets=list(definition.targets),
    )


def _source_can_trigger(
    definition: TriggerDefinition,
    event: TriggerEvent,
    game: GameState,
) -> bool:
    if game.zones.find_permanent(definition.source_permanent_id) is not None:
        return True
    return _is_self_leaves_battlefield_trigger(definition, event)


def _is_self_leaves_battlefield_trigger(
    definition: TriggerDefinition,
    event: TriggerEvent,
) -> bool:
    return (
        isinstance(event, ZoneMoveEvent)
        and isinstance(event.obj, Permanent)
        and definition.source_permanent_id == event.obj.obj_id
        and definition.trigger_key == TriggerKey.DIES
        and event.from_zone == Zone.BATTLEFIELD
    )
