"""Evoke: sacrifice on ETB when the creature was cast for evoke (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_evoke(perm: Permanent) -> bool:
    """Return True when the permanent has evoke."""
    return has_keyword(perm, 'Evoke')


def apply_evoke_on_etb(game: GameState, permanent: Permanent) -> str | None:
    """Sacrifice on ETB when cast with evoke (counter set at resolution)."""
    if not has_evoke(permanent):
        return None
    if not permanent.counters.get('evoked'):
        return None
    game.zones.leave_battlefield(permanent, Zone.GRAVEYARD, 'evoke', game)
    return f"evoked sacrifice {permanent.name}"


def mark_evoked_cast(permanent: Permanent) -> None:
    """Mark a permanent entering from an evoke cast."""
    permanent.counters['evoked'] = 1
