"""Evolve: +1/+1 when a larger creature enters under your control."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.ability_words.effects import _permanent_from_stack_source
from engine.core.game_object import Effect, GameObject, Permanent, effective_power
from engine.core.zones import Zone, ZoneMoveEvent
from engine.rules.triggers import TriggerDefinition, TriggerEvent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_evolve(perm: Permanent) -> bool:
    """Return True when the permanent has evolve."""
    return has_keyword(perm, 'Evolve')


def is_evolve_creature_enters(
    event: TriggerEvent,
    game: GameState,
    definition: TriggerDefinition,
) -> bool:
    """Evolve: a creature entered with power greater than this permanent's power."""
    if not (
        isinstance(event, ZoneMoveEvent)
        and event.to_zone == Zone.BATTLEFIELD
        and isinstance(event.obj, Permanent)
        and 'Creature' in event.obj.type_line
        and event.player_idx == definition.controller_idx
        and event.obj.obj_id != definition.source_permanent_id
    ):
        return False
    source = game.zones.find_permanent(definition.source_permanent_id)
    if source is None:
        return False
    return effective_power(event.obj) > effective_power(source)


class EvolveEffect(Effect):
    """Put a +1/+1 counter on the evolve source."""

    def resolve(self, game: GameState, source: GameObject) -> str:
        """Apply one +1/+1 counter."""
        permanent = _permanent_from_stack_source(game, source)
        if permanent is None:
            return ''
        put_plus_counters(permanent, 1)
        return f"{permanent.name} evolved (+1/+1)"

    def describe(self) -> str:
        """Return a short description for logs."""
        return 'Evolve (+1/+1)'
