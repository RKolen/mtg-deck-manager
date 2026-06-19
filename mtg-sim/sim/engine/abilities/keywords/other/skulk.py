"""Skulk: can only be blocked by creatures with equal or greater power."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent, effective_power


def has_skulk(perm: Permanent) -> bool:
    """Return True when the permanent has skulk."""
    return has_keyword(perm, 'Skulk')


def skulk_allows_block(blocker: Permanent, attacker: Permanent) -> bool:
    """Return True when a blocker may block a skulk attacker."""
    if not has_skulk(attacker):
        return True
    return effective_power(blocker) >= effective_power(attacker)
