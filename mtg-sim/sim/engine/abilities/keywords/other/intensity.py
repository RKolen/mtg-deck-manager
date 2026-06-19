"""Intensity: track intensity counters when you cast spells."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_INTENSITY_RE = re.compile(r'intensity\s+(\w+|\d+)', re.IGNORECASE)
_INTENSITY_COUNTER = 'intensity'


def has_intensity(perm: Permanent) -> bool:
    """Return True when the permanent has intensity."""
    return has_keyword(perm, 'Intensity')


def intensity_threshold(oracle_text: str) -> int:
    """Parse N from 'Intensity N'."""
    match = _INTENSITY_RE.search(oracle_text or '')
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_intensity_on_spell_cast(
    game: GameState,
    controller_idx: int,
    card: CardInfo | None,
) -> list[str]:
    """Increment intensity on each intensity permanent you control."""
    if card is None:
        return []
    details: list[str] = []
    for perm in game.zones.battlefield:
        if perm.controller_idx != controller_idx or not has_intensity(perm):
            continue
        perm.counters[_INTENSITY_COUNTER] = perm.counters.get(_INTENSITY_COUNTER, 0) + 1
        current = perm.counters[_INTENSITY_COUNTER]
        threshold = intensity_threshold(perm.oracle_text)
        if current >= threshold:
            details.append(f"intensity {perm.name} reached ({current})")
        else:
            details.append(f"intensity {perm.name} ({current}/{threshold})")
    return details
