"""Absorb: prevent N damage to this permanent."""

from __future__ import annotations

import re

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

_ABSORB_RE = re.compile(r'absorb\s+(\w+|\d+)', re.IGNORECASE)


def has_absorb(perm: Permanent) -> bool:
    """Return True when the permanent has absorb."""
    return has_keyword(perm, 'Absorb')


def absorb_amount(oracle_text: str) -> int:
    """Parse N from 'Absorb N'."""
    match = _ABSORB_RE.search(oracle_text)
    if match is None:
        return 0
    token = match.group(1)
    return int(token) if token.isdigit() else 0


def reduce_combat_damage(perm: Permanent, damage: int) -> int:
    """Reduce incoming combat damage by absorb amount."""
    if not has_absorb(perm):
        return damage
    return max(0, damage - absorb_amount(perm.oracle_text))
