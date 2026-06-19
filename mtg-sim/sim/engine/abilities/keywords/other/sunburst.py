"""Sunburst: +1/+1 counters for each color of mana in your mana pool on ETB."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_COLORLESS = frozenset({'C', 'S', ''})


def has_sunburst(perm: Permanent) -> bool:
    """Return True when the permanent has sunburst."""
    return has_keyword(perm, 'Sunburst')


def sunburst_counter_count(game: GameState, controller_idx: int) -> int:
    """Count distinct colored mana in the controller's mana pool."""
    colors = {
        mana.color
        for mana in game.players[controller_idx].mana_pool.pool
        if mana.color not in _COLORLESS
    }
    return len(colors)


def apply_sunburst_etb(game: GameState, permanent: Permanent) -> str | None:
    """Put +1/+1 counters on the permanent for each color in the mana pool."""
    if not has_sunburst(permanent):
        return None
    count = sunburst_counter_count(game, permanent.controller_idx)
    if count > 0:
        put_plus_counters(permanent, count)
    return f"sunburst {permanent.name} ({count} counter(s))"
