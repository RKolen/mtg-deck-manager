"""Haunt: when this creature dies, exile it haunting another creature (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import CardObject, Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_HAUNTED_COUNTER = 'haunted'


def has_haunt(perm: Permanent) -> bool:
    """Return True when the permanent has haunt."""
    return has_keyword(perm, 'Haunt')


def is_haunted(perm: Permanent) -> bool:
    """Return True when a creature is haunted."""
    return perm.counters.get(_HAUNTED_COUNTER, 0) > 0


def apply_haunt_on_creature_death(
    game: GameState,
    dying: Permanent,
) -> str | None:
    """Exile a haunt creature and mark an opponent creature as haunted."""
    if not has_haunt(dying) or 'Creature' not in dying.type_line:
        return None
    controller = dying.controller_idx
    opponent = 1 - controller
    targets = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == opponent and 'Creature' in perm.type_line
    ]
    graveyard = game.zones.player_zones[controller].graveyard
    card = dying.source
    if isinstance(card, CardObject) and card in graveyard:
        graveyard.remove(card)
        game.zones.player_zones[controller].exile.append(card)
    if not targets:
        return f"haunt exiled {dying.name} (no target)"
    haunted = targets[0]
    haunted.counters[_HAUNTED_COUNTER] = 1
    return f"haunt exiled {dying.name} haunting {haunted.name}"


def clear_haunt_on_leave_battlefield(perm: Permanent) -> None:
    """Remove haunt marker when a haunted creature leaves the battlefield."""
    perm.counters.pop(_HAUNTED_COUNTER, None)
