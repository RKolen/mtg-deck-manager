"""Triggered ability registration and firing helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from engine.core.game_object import Effect, Permanent, Target, TriggeredAbilityOnStack
from engine.core.game_state import GameState
from engine.core.zones import Zone, ZoneMoveEvent


class TriggerKey(StrEnum):
    """Known trigger timing/event keys."""

    ENTERS_BATTLEFIELD = "enters_battlefield"


TriggerCondition = Callable[[ZoneMoveEvent, GameState], bool]


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
        event: ZoneMoveEvent,
        game: GameState,
    ) -> list[TriggeredAbilityOnStack]:
        """Return triggered abilities that fire from the event."""
        return [
            _to_stack_object(definition)
            for definition in self._definitions
            if _source_still_exists(definition, game)
            and definition.condition(event, game)
        ]

    def put_triggers_on_stack(
        self,
        event: ZoneMoveEvent,
        game: GameState,
    ) -> list[TriggeredAbilityOnStack]:
        """Create triggered abilities and put them on the game stack."""
        abilities = self.fire(event, game)
        for ability in abilities:
            game.stack.push(ability)
        return abilities


def is_enters_battlefield(event: ZoneMoveEvent, _game: GameState) -> bool:
    """Return True when an event moved an object onto the battlefield."""
    return event.to_zone == Zone.BATTLEFIELD


def _to_stack_object(definition: TriggerDefinition) -> TriggeredAbilityOnStack:
    return TriggeredAbilityOnStack(
        controller_idx=definition.controller_idx,
        owner_idx=definition.controller_idx,
        source_permanent_id=definition.source_permanent_id,
        trigger_key=definition.trigger_key.value,
        effect=definition.effect,
        targets=list(definition.targets),
    )


def _source_still_exists(definition: TriggerDefinition, game: GameState) -> bool:
    return game.zones.find_permanent(definition.source_permanent_id) is not None
