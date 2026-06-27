"""Hexproof from: opponents cannot target with specific kinds of sources."""

from __future__ import annotations

import re

from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

_HEXPROOF_FROM_RE = re.compile(
    r'hexproof\s+from\s+([\w\s]+?)(?=\.|,|\n|$)',
    re.IGNORECASE,
)
_QUALITY_MAP = {
    'creatures': 'creatures',
    'creature': 'creatures',
    'artifacts': 'artifacts',
    'artifact': 'artifacts',
    'enchantments': 'enchantments',
    'enchantment': 'enchantments',
    'instants': 'instants',
    'instant': 'instants',
    'sorceries': 'sorceries',
    'sorcery': 'sorceries',
    'planeswalkers': 'planeswalkers',
    'planeswalker': 'planeswalkers',
    'red': 'red',
    'blue': 'blue',
    'black': 'black',
    'white': 'white',
    'green': 'green',
}


def has_hexproof_from(perm: Permanent) -> bool:
    """Return True when the permanent has hexproof from."""
    text = perm.oracle_text or ''
    return has_registered_keyword(text, 'Hexproof from') or bool(
        _HEXPROOF_FROM_RE.search(text)
    )


def hexproof_from_qualities(perm: Permanent) -> frozenset[str]:
    """Return qualities this permanent has hexproof from."""
    text = perm.oracle_text or ''
    found = {
        _normalize_quality(match.group(1))
        for match in _HEXPROOF_FROM_RE.finditer(text)
    }
    return frozenset(q for q in found if q)


def _normalize_quality(text: str) -> str:
    lowered = text.strip().lower()
    return _QUALITY_MAP.get(lowered, lowered)
