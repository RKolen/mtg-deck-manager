"""Horsemanship: only creatures with horsemanship can block this creature."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent


def has_horsemanship(perm: Permanent) -> bool:
    """Return True when the permanent has horsemanship."""
    return has_keyword(perm, 'Horsemanship')


def horsemanship_allows_block(blocker: Permanent, attacker: Permanent) -> bool:
    """Return True when blocker may block a horsemanship attacker."""
    if not has_horsemanship(attacker):
        return True
    return has_horsemanship(blocker)
