"""
Rules hooks for keyword abilities integrated into the engine (Phase E).

Handlers are invoked from combat, zone changes, and casting where the simplified
engine supports them. Keywords only detected in the registry still parse correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords import has_deathtouch, has_infect, has_wither
from engine.core.game_object import Permanent, TokenObject

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_REGENERATION_SHIELD = 'regeneration shield'


def apply_combat_damage_to_creature(
    receiver: Permanent,
    source: Permanent,
    damage: int,
) -> None:
    """Apply combat damage respecting infect, wither, and deathtouch."""
    if damage <= 0:
        return
    if has_infect(source):
        receiver.counters['-1/-1'] = receiver.counters.get('-1/-1', 0) + damage
        return
    if has_wither(source):
        receiver.counters['-1/-1'] = receiver.counters.get('-1/-1', 0) + damage
        return
    receiver.damage_marked += damage
    if has_deathtouch(source):
        toughness = _effective_toughness(receiver)
        receiver.damage_marked = max(receiver.damage_marked, toughness)


def grant_regeneration_shield(perm: Permanent) -> None:
    """Mark a permanent with a regeneration shield (simplified regenerate)."""
    perm.counters[_REGENERATION_SHIELD] = 1


def consume_regeneration_shield(perm: Permanent) -> bool:
    """Consume shield if present; return True when damage/destruction is prevented."""
    if perm.counters.get(_REGENERATION_SHIELD, 0) <= 0:
        return False
    perm.counters[_REGENERATION_SHIELD] = 0
    perm.damage_marked = 0
    return True


def storm_copy_count(game: GameState) -> int:
    """Return number of storm copies (spells cast this turn including this one)."""
    active = game.active_player_idx
    return game.players[active].spells_cast_this_turn


def _effective_toughness(perm: Permanent) -> int:
    if perm.card_info is not None:
        try:
            raw = perm.card_info.pt.split('/', maxsplit=1)[1]
            base = int(raw)
        except (ValueError, TypeError, IndexError):
            base = 1
    elif isinstance(perm.source, TokenObject):
        try:
            base = int(perm.source.toughness)
        except (ValueError, TypeError):
            base = 1
    else:
        base = 1
    return base + perm.counters.get('+1/+1', 0) - perm.counters.get('-1/-1', 0)
