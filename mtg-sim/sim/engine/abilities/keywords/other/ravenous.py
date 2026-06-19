"""Ravenous: enters with +1/+1 counters for each card in your hand."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_RAVENOUS_RE = re.compile(r'ravenous\s+(\w+|\d+)', re.IGNORECASE)


def has_ravenous(perm: Permanent) -> bool:
    """Return True when the permanent has ravenous."""
    return has_keyword(perm, 'Ravenous')


def ravenous_multiplier(oracle_text: str) -> int:
    """Parse N from 'Ravenous N' (counters per card)."""
    match = _RAVENOUS_RE.search(oracle_text or '')
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_ravenous_etb(game: GameState, permanent: Permanent) -> str | None:
    """Put +1/+1 counters on the permanent for each card in hand."""
    if not has_ravenous(permanent):
        return None
    hand_size = len(game.zones.player_zones[permanent.controller_idx].hand)
    amount = hand_size * ravenous_multiplier(permanent.oracle_text)
    if amount > 0:
        permanent.counters['+1/+1'] = permanent.counters.get('+1/+1', 0) + amount
    return f"ravenous {permanent.name} ({amount} counter(s))"
