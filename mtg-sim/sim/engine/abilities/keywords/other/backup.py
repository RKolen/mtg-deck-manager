"""Backup: ETB put +1/+1 counters on another creature you control."""

from __future__ import annotations

import re

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.other.host_creature import find_host_creature
from engine.core.game_object import Permanent

_BACKUP_RE = re.compile(r'backup\s+(\w+|\d+)', re.IGNORECASE)


def has_backup(perm: Permanent) -> bool:
    """Return True when the permanent has backup."""
    return has_keyword(perm, 'Backup')


def backup_amount(oracle_text: str) -> int:
    """Parse N from 'Backup N'."""
    match = _BACKUP_RE.search(oracle_text)
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_backup_etb(permanent: Permanent, battlefield: list[Permanent]) -> str | None:
    """Put backup counters on another creature you control."""
    if not has_backup(permanent):
        return None
    amount = backup_amount(permanent.oracle_text)
    target = find_host_creature(permanent, battlefield)
    if target is None:
        return None
    put_plus_counters(target, amount)
    return f"backup +{amount}/+{amount} on {target.name}"
