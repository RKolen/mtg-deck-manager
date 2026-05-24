"""Renown: +1/+1 counter and renowned when dealing combat damage to a player."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent

_RENOWNED_COUNTER = 'renowned'


def has_renown(perm: Permanent) -> bool:
    """Return True when the permanent has renown."""
    return has_keyword(perm, 'Renown')


def is_renowned(perm: Permanent) -> bool:
    """Return True when the permanent is already renowned."""
    return perm.counters.get(_RENOWNED_COUNTER, 0) > 0


def apply_renown_on_combat_damage_to_player(
    attacker: Permanent,
    damage: int,
) -> str | None:
    """Put a +1/+1 counter on the attacker and mark it renowned."""
    if damage <= 0 or not has_renown(attacker) or is_renowned(attacker):
        return None
    put_plus_counters(attacker, 1)
    attacker.counters[_RENOWNED_COUNTER] = 1
    return f"{attacker.name} renowned (+1/+1)"
