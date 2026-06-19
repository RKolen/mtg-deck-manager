"""Tribute: opponent chooses +1/+1 or an effect on ETB (simplified: +1/+1)."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent


def has_tribute(perm: Permanent) -> bool:
    """Return True when the permanent has tribute."""
    return has_keyword(perm, 'Tribute')


def apply_tribute_etb(permanent: Permanent) -> str | None:
    """Apply tribute: simplified opponent choice grants +1/+1."""
    if not has_tribute(permanent):
        return None
    permanent.counters['+1/+1'] = permanent.counters.get('+1/+1', 0) + 1
    return f"tribute {permanent.name} (+1/+1)"
