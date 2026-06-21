"""Saddle: creatures can tap to help saddle a Mount (simplified detection)."""

from __future__ import annotations

import re

from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

_SADDLE_RE = re.compile(r'saddle\s*(\d+)', re.IGNORECASE)


def has_saddle(perm: Permanent) -> bool:
    """Return True when the permanent has saddle."""
    oracle = perm.oracle_text or ''
    return has_registered_keyword(oracle, 'Saddle') or bool(
        _SADDLE_RE.search(oracle)
    )


def saddle_amount(oracle_text: str) -> int:
    """Return N from Saddle N."""
    match = _SADDLE_RE.search(oracle_text or '')
    if match is None:
        return 0
    return int(match.group(1))
