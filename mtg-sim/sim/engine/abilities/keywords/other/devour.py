"""Devour: sacrifice creatures on ETB for +1/+1 counters."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent, effective_power
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_DEVOUR_RE = re.compile(r'devour\s+(\w+|\d+)', re.IGNORECASE)


def has_devour(perm: Permanent) -> bool:
    """Return True when the permanent has devour."""
    return has_keyword(perm, 'Devour')


def devour_amount(oracle_text: str) -> int:
    """Parse N from 'Devour N'."""
    match = _DEVOUR_RE.search(oracle_text)
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_devour_etb(game: GameState, permanent: Permanent) -> str | None:
    """Sacrifice up to N other creatures you control for +1/+1 each (simplified)."""
    if not has_devour(permanent):
        return None
    amount = devour_amount(permanent.oracle_text)
    candidates = [
        perm
        for perm in game.zones.battlefield
        if perm.controller_idx == permanent.controller_idx
        and perm.obj_id != permanent.obj_id
        and 'Creature' in perm.type_line
    ]
    candidates.sort(key=effective_power)
    sacrificed = 0
    for victim in candidates[:amount]:
        game.zones.leave_battlefield(victim, Zone.GRAVEYARD, 'devour', game)
        sacrificed += 1
    if sacrificed:
        put_plus_counters(permanent, sacrificed)
    return f"devoured {sacrificed} creature(s) (+{sacrificed}/+{sacrificed})"
