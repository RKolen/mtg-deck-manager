"""Runtime handlers invoked from combat, SBAs, and casting."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.combat import has_deathtouch
from engine.abilities.keywords.counters import has_infect, has_wither
from engine.core.game_object import Permanent, effective_toughness
from engine.rules.replacement import (
    apply_damage_with_replacements,
    consume_regeneration_shield,
    grant_regeneration_shield,
)

if TYPE_CHECKING:
    from engine.core.game_state import GameState

__all__ = [
    'apply_combat_damage_to_creature',
    'apply_damage_to_permanent',
    'consume_regeneration_shield',
    'grant_regeneration_shield',
    'storm_copy_count',
]


def apply_damage_to_permanent(
    receiver: Permanent,
    damage: int,
    game: GameState,
    *,
    source: Permanent | None = None,
) -> int:
    """Apply damage from any source; return the amount marked on the permanent."""
    if damage <= 0:
        return 0
    damage = apply_damage_with_replacements(game, receiver, source, damage)
    if damage <= 0:
        return 0
    receiver.damage_marked += damage
    return damage


def apply_combat_damage_to_creature(
    receiver: Permanent,
    source: Permanent,
    damage: int,
    game: GameState | None = None,
) -> None:
    """Apply combat damage respecting infect, wither, deathtouch, and replacements."""
    if damage <= 0:
        return
    if has_infect(source, game):
        receiver.counters['-1/-1'] = receiver.counters.get('-1/-1', 0) + damage
        return
    if has_wither(source, game):
        receiver.counters['-1/-1'] = receiver.counters.get('-1/-1', 0) + damage
        return
    damage = apply_damage_with_replacements(game, receiver, source, damage)
    if damage <= 0:
        return
    receiver.damage_marked += damage
    if has_deathtouch(source, game):
        toughness = effective_toughness(receiver, game)
        receiver.damage_marked = max(receiver.damage_marked, toughness)


def storm_copy_count(game: GameState) -> int:
    """Return number of storm copies for the active player's cast count."""
    active = game.active_player_idx
    count = game.players[active].spells_cast_this_turn
    return max(0, count - 1)
