"""Encore: mark permanents that can be given encore (simplified)."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent


def has_encore(perm: Permanent) -> bool:
    """Return True when the permanent has encore."""
    return has_keyword(perm, 'Encore')


def apply_encore_etb(permanent: Permanent) -> str | None:
    """Mark encore on ETB (simplified; token copy not modeled)."""
    if not has_encore(permanent):
        return None
    permanent.counters['encore'] = 1
    return f"{permanent.name} has encore"
