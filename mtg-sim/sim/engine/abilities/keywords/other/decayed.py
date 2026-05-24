"""Decayed: cannot attack; sacrifice at end of turn."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_DECAYED_COUNTER = 'decayed'


def has_decayed(perm: Permanent) -> bool:
    """Return True when the permanent is decayed."""
    return perm.counters.get(_DECAYED_COUNTER, 0) > 0


def apply_decayed_etb(permanent: Permanent) -> str | None:
    """Mark a creature decayed on ETB."""
    if not has_keyword(permanent, 'Decayed'):
        return None
    permanent.counters[_DECAYED_COUNTER] = 1
    return f"{permanent.name} entered with decayed"


def blocks_attack(perm: Permanent) -> bool:
    """Return True when decayed prevents attacking."""
    return has_decayed(perm)


def sacrifice_decayed_creatures(game: GameState, player_idx: int) -> list[str]:
    """Sacrifice decayed creatures at end of turn."""
    details: list[str] = []
    for perm in list(game.zones.battlefield):
        if perm.controller_idx != player_idx:
            continue
        if not perm.counters.pop(_DECAYED_COUNTER, 0):
            continue
        game.zones.leave_battlefield(perm, Zone.GRAVEYARD, 'decayed', game)
        details.append(f"{perm.name} sacrificed (decayed)")
    return details
