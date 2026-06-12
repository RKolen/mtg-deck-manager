"""Flanking: blocking creatures without flanking get -1/-1 (CR 702.36, simplified)."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent


def has_flanking(perm: Permanent) -> bool:
    """Return True when the permanent has flanking."""
    return has_keyword(perm, 'Flanking')


def apply_flanking_on_block(attacker: Permanent, blocker: Permanent) -> str | None:
    """Give a blocker -1/-1 when blocked by a creature with flanking."""
    if not has_flanking(attacker) or has_flanking(blocker):
        return None
    blocker.counters['-1/-1'] = blocker.counters.get('-1/-1', 0) + 1
    return f"flanking -1/-1 on {blocker.name}"
