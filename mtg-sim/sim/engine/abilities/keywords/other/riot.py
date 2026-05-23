"""Riot: enter with your choice of +1/+1 counter or haste."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_riot(perm: Permanent) -> bool:
    """Return True when the permanent has riot."""
    return has_keyword(perm, 'Riot')


def apply_riot_etb(permanent: Permanent) -> str | None:
    """Apply riot on ETB: +1/+1 counter (simplified default)."""
    if not has_riot(permanent):
        return None
    put_plus_counters(permanent, 1)
    return f"riot +1/+1 on {permanent.name}"
