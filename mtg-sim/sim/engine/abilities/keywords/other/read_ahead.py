"""Read ahead: Sagas enter with extra lore counters (simplified)."""

from __future__ import annotations

import re

from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

_READ_AHEAD_RE = re.compile(r'read ahead\s+(\d+)', re.IGNORECASE)


def has_read_ahead(perm: Permanent) -> bool:
    """Return True when the permanent has read ahead."""
    oracle = perm.oracle_text or ''
    return has_registered_keyword(oracle, 'Read Ahead') or bool(
        _READ_AHEAD_RE.search(oracle)
    )


def read_ahead_amount(oracle_text: str) -> int:
    """Return N from Read ahead N."""
    match = _READ_AHEAD_RE.search(oracle_text or '')
    if match is None:
        return 1
    return int(match.group(1))


def apply_read_ahead_etb(permanent: Permanent) -> str | None:
    """Put lore counters on a Saga with read ahead."""
    if not has_read_ahead(permanent):
        return None
    if 'Saga' not in permanent.type_line:
        return None
    extra = read_ahead_amount(permanent.oracle_text)
    permanent.counters['lore'] = permanent.counters.get('lore', 0) + 1 + extra
    return f"read ahead {permanent.name} ({1 + extra} lore)"
