"""Graft: move a +1/+1 counter from another creature on ETB (CR 702.41, simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.other.host_creature import find_host_creature
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_graft(perm: Permanent) -> bool:
    """Return True when the permanent has graft."""
    return has_keyword(perm, 'Graft')


def apply_graft_etb(game: GameState, permanent: Permanent) -> str | None:
    """Move one +1/+1 counter from another creature you control onto this creature."""
    if not has_graft(permanent):
        return None
    donor = find_host_creature(
        permanent,
        game.zones.battlefield,
        exclude=lambda perm: perm.counters.get('+1/+1', 0) <= 0,
    )
    if donor is None:
        return f"graft {permanent.name} (no donor)"
    donor.counters['+1/+1'] -= 1
    if donor.counters['+1/+1'] <= 0:
        donor.counters.pop('+1/+1', None)
    put_plus_counters(permanent, 1)
    return f"graft moved +1/+1 from {donor.name} to {permanent.name}"
