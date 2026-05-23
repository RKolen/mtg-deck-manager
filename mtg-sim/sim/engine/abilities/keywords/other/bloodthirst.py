"""Bloodthirst: ETB with +1/+1 counters if an opponent was dealt damage this turn."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions._parse import word_to_int
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_BLOODTHIRST_RE = re.compile(r'bloodthirst\s+(\w+|\d+)', re.IGNORECASE)


def has_bloodthirst(perm: Permanent) -> bool:
    """Return True when the permanent has bloodthirst."""
    return has_keyword(perm, 'Bloodthirst')


def bloodthirst_amount(oracle_text: str) -> int:
    """Parse N from 'Bloodthirst N'."""
    match = _BLOODTHIRST_RE.search(oracle_text)
    if match is None:
        return 1
    return word_to_int(match.group(1))


def apply_bloodthirst_etb(game: GameState, permanent: Permanent) -> str | None:
    """Put bloodthirst counters on ETB when an opponent was dealt damage this turn."""
    if not has_bloodthirst(permanent):
        return None
    opponent = 1 - permanent.controller_idx
    if not game.players[opponent].was_dealt_damage_this_turn:
        return None
    amount = bloodthirst_amount(permanent.oracle_text)
    put_plus_counters(permanent, amount)
    return f"bloodthirst +{amount}/+{amount} on {permanent.name}"
