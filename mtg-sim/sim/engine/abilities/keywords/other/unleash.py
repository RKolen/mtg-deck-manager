"""Unleash: +1/+1 counter and cannot block (simplified choice: always unleash)."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

_UNLEASH_NO_BLOCK = 'unleash_no_block'


def has_unleash(perm: Permanent) -> bool:
    """Return True when the permanent has unleash."""
    return has_keyword(perm, 'Unleash')


def unleash_prevents_block(perm: Permanent) -> bool:
    """Return True when unleash prevents this creature from blocking."""
    return perm.counters.get(_UNLEASH_NO_BLOCK, 0) > 0


def apply_unleash_etb(permanent: Permanent) -> str | None:
    """Put a +1/+1 counter on the creature and mark it unable to block."""
    if not has_unleash(permanent):
        return None
    permanent.counters['+1/+1'] = permanent.counters.get('+1/+1', 0) + 1
    permanent.counters[_UNLEASH_NO_BLOCK] = 1
    return f"unleash {permanent.name} (+1/+1, can't block)"
