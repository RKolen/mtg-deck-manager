"""Rampage: bonus when blocked by more than one creature."""

from __future__ import annotations

import re

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent

_RAMPAGE_RE = re.compile(r'rampage\s+(\w+|\d+)', re.IGNORECASE)


def has_rampage(perm: Permanent) -> bool:
    """Return True when the permanent has rampage."""
    return has_keyword(perm, 'Rampage')


def rampage_amount(oracle_text: str) -> int:
    """Parse N from 'Rampage N'."""
    match = _RAMPAGE_RE.search(oracle_text or '')
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_rampage_on_block(
    attacker: Permanent,
    blockers: list[Permanent],
) -> str | None:
    """Put +N/+N counters when blocked by two or more creatures."""
    if not has_rampage(attacker) or len(blockers) < 2:
        return None
    amount = rampage_amount(attacker.oracle_text) * (len(blockers) - 1)
    put_plus_counters(attacker, amount)
    return f"rampage {attacker.name} (+{amount}/+{amount})"
