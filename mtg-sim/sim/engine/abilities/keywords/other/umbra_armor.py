"""Umbra armor: aura is exiled instead of the enchanted creature dying once."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_umbra_armor(perm: Permanent) -> bool:
    """Return True when the aura has umbra armor."""
    if 'Aura' not in perm.type_line and 'Enchantment' not in perm.type_line:
        return False
    return has_keyword(perm, 'Umbra armor')


def try_umbra_armor_replacement(game: GameState, creature: Permanent) -> bool:
    """Exile an umbra armor aura instead of destroying the enchanted creature."""
    if 'Creature' not in creature.type_line:
        return False
    for aura in game.zones.battlefield:
        if aura.attached_to != creature.obj_id or not has_umbra_armor(aura):
            continue
        game.zones.leave_battlefield(aura, Zone.EXILE, 'umbra_armor', game)
        creature.damage_marked = 0
        game.log_event(
            'rules',
            'umbra_armor',
            f'{aura.name} saved {creature.name}',
        )
        return True
    return False
