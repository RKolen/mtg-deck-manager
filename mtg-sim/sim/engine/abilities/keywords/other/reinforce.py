"""Reinforce: discard cards for +1/+1 counters on ETB (simplified)."""

from __future__ import annotations

import re

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent

_REINFORCE_RE = re.compile(r'reinforce\s+(\d+)', re.IGNORECASE)


def has_reinforce(perm: Permanent) -> bool:
    """Return True when the permanent has reinforce."""
    oracle = perm.oracle_text or ''
    return has_keyword(perm, 'Reinforce') or bool(_REINFORCE_RE.search(oracle))


def reinforce_amount(oracle_text: str) -> int:
    """Parse N from 'Reinforce N'."""
    match = _REINFORCE_RE.search(oracle_text or '')
    if match is None:
        return 1
    return int(match.group(1))


def apply_reinforce_etb(permanent: Permanent) -> str | None:
    """Apply reinforce: simplified discard grants +1/+1 equal to reinforce N."""
    if not has_reinforce(permanent):
        return None
    amount = reinforce_amount(permanent.oracle_text)
    if amount <= 0:
        return None
    put_plus_counters(permanent, amount)
    return f"reinforce {permanent.name} (+{amount}/+{amount})"
