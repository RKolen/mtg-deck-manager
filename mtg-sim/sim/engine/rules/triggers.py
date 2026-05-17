"""Triggered ability registration and firing helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from engine.core.game_object import CardObject, Effect, Permanent, Target
from engine.core.game_object import TriggeredAbilityOnStack
from engine.core.turn_structure import Step
from engine.core.zones import Zone, ZoneMoveEvent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


class TriggerKey(StrEnum):
    """Known trigger timing/event keys."""

    ENTERS_BATTLEFIELD = "enters_battlefield"
    LEAVES_BATTLEFIELD = "leaves_battlefield"
    DIES = "dies"
    ATTACKS = "attacks"
    BLOCKS = "blocks"
    BEGINNING_OF_UPKEEP = "beginning_of_upkeep"
    BEGINNING_OF_COMBAT = "beginning_of_combat"
    END_STEP = "end_step"
    DRAWS_CARD = "draws_card"
    SPELL_CAST = "spell_cast"
    LIFE_GAINED = "life_gained"
    DEALS_COMBAT_DAMAGE = "deals_combat_damage"


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


@dataclass(frozen=True)
class BlockTriggerEvent:
    """Synthetic event emitted when a blocker is declared."""

    blocker_id: int
    attacker_id: int
    defending_player_idx: int


@dataclass(frozen=True)
class SpellCastTriggerEvent:
    """Synthetic event emitted when a spell is cast."""

    spell_id: int
    controller_idx: int
    spell_name: str
    type_line: str
    targets: tuple[Target, ...] = ()


@dataclass(frozen=True)
class LifeGainedTriggerEvent:
    """Synthetic event emitted when a player gains life."""

    player_idx: int
    amount: int
    source_permanent_id: int | None = None


@dataclass(frozen=True)
class CombatDamageTriggerEvent:
    """Synthetic event emitted when a permanent deals combat damage."""

    source_permanent_id: int
    controller_idx: int
    amount: int
    damaged_player_idx: int | None = None
    damaged_permanent_id: int | None = None


TriggerEvent = (
    ZoneMoveEvent
    | StepTriggerEvent
    | AttackTriggerEvent
    | BlockTriggerEvent
    | SpellCastTriggerEvent
    | LifeGainedTriggerEvent
    | CombatDamageTriggerEvent
)
TriggerCondition = Callable[[TriggerEvent, "GameState", "TriggerDefinition"], bool]


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
            and definition.condition(event, game, definition)
        ]

    def put_triggers_on_stack(
        self,
        event: TriggerEvent,
        game: GameState,
    ) -> list[TriggeredAbilityOnStack]:
        """Create triggered abilities and put them on the game stack."""
        abilities = _order_apnap(self.fire(event, game), game.active_player_idx)
        for ability in abilities:
            game.stack.push(ability)
        return abilities


def is_enters_battlefield(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when an event moved an object onto the battlefield."""
    return isinstance(event, ZoneMoveEvent) and event.to_zone == Zone.BATTLEFIELD


def is_leaves_battlefield(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when an event moved an object away from the battlefield."""
    return isinstance(event, ZoneMoveEvent) and event.from_zone == Zone.BATTLEFIELD


def is_dies(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when a creature moved from battlefield to graveyard."""
    return (
        isinstance(event, ZoneMoveEvent)
        and isinstance(event.obj, Permanent)
        and event.from_zone == Zone.BATTLEFIELD
        and event.to_zone == Zone.GRAVEYARD
        and "Creature" in event.obj.type_line
    )


def is_attacks(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when an attacker is declared."""
    return isinstance(event, AttackTriggerEvent)


def is_blocks(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when a blocker is declared."""
    return isinstance(event, BlockTriggerEvent)


def is_beginning_of_upkeep(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when upkeep begins."""
    return isinstance(event, StepTriggerEvent) and event.step == Step.UPKEEP


def is_beginning_of_combat(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when beginning of combat begins."""
    return isinstance(event, StepTriggerEvent) and event.step == Step.BEGIN_COMBAT


def is_end_step(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when the end step begins."""
    return isinstance(event, StepTriggerEvent) and event.step == Step.END_STEP


def is_draws_card(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when a card is drawn from library into hand."""
    return (
        isinstance(event, ZoneMoveEvent)
        and event.from_zone == Zone.LIBRARY
        and event.to_zone == Zone.HAND
        and event.cause == "draw"
    )


def is_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when a spell is cast."""
    return isinstance(event, SpellCastTriggerEvent)


def is_life_gained(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when a player gains life."""
    return isinstance(event, LifeGainedTriggerEvent) and event.amount > 0


def is_controller_gains_life(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Return True when this trigger's controller gains life."""
    return (
        isinstance(event, LifeGainedTriggerEvent)
        and event.player_idx == definition.controller_idx
        and event.amount > 0
    )


def is_deals_combat_damage(
    event: TriggerEvent,
    _game: GameState,
    _definition: TriggerDefinition,
) -> bool:
    """Return True when a permanent deals combat damage."""
    return isinstance(event, CombatDamageTriggerEvent) and event.amount > 0


def is_source_deals_combat_damage(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Return True when this trigger's source deals combat damage."""
    return (
        isinstance(event, CombatDamageTriggerEvent)
        and event.source_permanent_id == definition.source_permanent_id
        and event.amount > 0
    )


def is_noncreature_nonland_spell_cast(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Return True when this trigger's controller casts a noncreature nonland spell."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and "Creature" not in event.type_line
        and "Land" not in event.type_line
    )


def is_spell_targeting_source(
    event: TriggerEvent,
    _game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Return True when this trigger's controller casts a spell targeting its source."""
    return (
        isinstance(event, SpellCastTriggerEvent)
        and event.controller_idx == definition.controller_idx
        and any(target.obj_id == definition.source_permanent_id for target in event.targets)
    )


def spell_cast_event(
    spell: CardObject,
    targets: tuple[Target, ...] = (),
) -> SpellCastTriggerEvent:
    """Build a spell-cast event from a card object."""
    card_info = spell.card_info
    return SpellCastTriggerEvent(
        spell_id=spell.obj_id,
        controller_idx=spell.controller_idx,
        spell_name=card_info.name if card_info is not None else "",
        type_line=card_info.type_line if card_info is not None else "",
        targets=targets,
    )


def _to_stack_object(definition: TriggerDefinition) -> TriggeredAbilityOnStack:
    return TriggeredAbilityOnStack(
        controller_idx=definition.controller_idx,
        owner_idx=definition.controller_idx,
        source_permanent_id=definition.source_permanent_id,
        trigger_key=definition.trigger_key.value,
        effect=definition.effect,
        targets=list(definition.targets),
    )


def _order_apnap(
    abilities: list[TriggeredAbilityOnStack],
    active_player_idx: int,
) -> list[TriggeredAbilityOnStack]:
    """Return abilities in APNAP order for placement on the stack."""
    return sorted(
        abilities,
        key=lambda ability: ability.controller_idx != active_player_idx,
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
        and definition.trigger_key in (
            TriggerKey.DIES,
            TriggerKey.LEAVES_BATTLEFIELD,
        )
        and event.from_zone == Zone.BATTLEFIELD
    )
