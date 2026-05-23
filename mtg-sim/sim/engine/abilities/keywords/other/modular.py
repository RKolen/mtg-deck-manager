"""Modular: ETB counters and move counters to another artifact when this dies."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_MODULAR_RE = re.compile(r'modular\s+(\w+|\d+)', re.IGNORECASE)


def has_modular(perm: Permanent) -> bool:
    """Return True when the permanent has modular."""
    return has_keyword(perm, 'Modular')


def modular_amount(oracle_text: str) -> int:
    """Parse N from 'Modular N'."""
    match = _MODULAR_RE.search(oracle_text)
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_modular_etb(permanent: Permanent) -> str | None:
    """Enter the battlefield with N +1/+1 counters."""
    if not has_modular(permanent):
        return None
    amount = modular_amount(permanent.oracle_text)
    put_plus_counters(permanent, amount)
    return f"modular +{amount}/+{amount} on {permanent.name}"


def apply_modular_on_die(game: GameState, dying: Permanent) -> str | None:
    """Move +1/+1 counters from a dying modular permanent to another artifact."""
    if not has_modular(dying):
        return None
    counters = dying.counters.get('+1/+1', 0)
    if counters <= 0:
        return None
    recipient = next(
        (
            perm
            for perm in game.zones.battlefield
            if perm.controller_idx == dying.controller_idx
            and perm.obj_id != dying.obj_id
            and 'Artifact' in perm.type_line
        ),
        None,
    )
    if recipient is None:
        return None
    recipient.counters['+1/+1'] = recipient.counters.get('+1/+1', 0) + counters
    dying.counters['+1/+1'] = 0
    return f"modular moved {counters} counter(s) to {recipient.name}"
