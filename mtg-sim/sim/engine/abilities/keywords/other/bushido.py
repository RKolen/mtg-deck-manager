"""Bushido: +N/+N when this creature blocks or becomes blocked."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent

_BUSHIDO_RE = re.compile(r'bushido\s+(\w+|\d+)', re.IGNORECASE)


def has_bushido(perm: Permanent) -> bool:
    """Return True when the permanent has bushido."""
    return has_keyword(perm, 'Bushido')


def has_bushido_card(card: CardInfo) -> bool:
    """Return True when the card has bushido."""
    return has_registered_keyword(card.oracle_text, 'Bushido')


def bushido_amount(oracle_text: str) -> int:
    """Parse N from 'Bushido N' (default 1)."""
    match = _BUSHIDO_RE.search(oracle_text)
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_bushido_when_engaged(perm: Permanent) -> str | None:
    """Apply bushido once when the creature is engaged in combat."""
    if not has_bushido(perm) or perm.counters.get('bushido_applied'):
        return None
    amount = bushido_amount(perm.oracle_text)
    put_plus_counters(perm, amount)
    perm.counters['bushido_applied'] = 1
    return f"bushido +{amount}/+{amount} on {perm.name}"


def clear_bushido_combat_markers(perm: Permanent) -> None:
    """Clear bushido combat markers at the start of a new turn."""
    perm.counters.pop('bushido_applied', None)
