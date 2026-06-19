"""Vanishing: enters with time counters; removed each upkeep; dies at zero."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_VANISH_RE = re.compile(r'vanishing\s+(\w+|\d+)', re.IGNORECASE)
_TIME_COUNTER = 'time'


def has_vanishing(perm: Permanent) -> bool:
    """Return True when the permanent has vanishing."""
    return has_keyword(perm, 'Vanishing')


def vanishing_amount(oracle_text: str) -> int:
    """Parse N from 'Vanishing N'."""
    match = _VANISH_RE.search(oracle_text or '')
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_vanishing_etb(permanent: Permanent) -> str | None:
    """Put time counters on the permanent when it enters."""
    if not has_vanishing(permanent):
        return None
    amount = vanishing_amount(permanent.oracle_text)
    permanent.counters[_TIME_COUNTER] = amount
    return f"vanishing {permanent.name} ({amount} time)"


def resolve_vanishing_upkeep(game: GameState, player_idx: int) -> list[str]:
    """Remove a time counter from each vanishing permanent; sacrifice at zero."""
    details: list[str] = []
    for perm in list(game.zones.battlefield):
        if perm.controller_idx != player_idx or not has_vanishing(perm):
            continue
        remaining = perm.counters.get(_TIME_COUNTER, 0)
        if remaining <= 0:
            continue
        perm.counters[_TIME_COUNTER] = remaining - 1
        if perm.counters[_TIME_COUNTER] <= 0:
            game.zones.leave_battlefield(perm, Zone.GRAVEYARD, 'vanishing', game)
            details.append(f"vanishing sacrificed {perm.name}")
        else:
            details.append(
                f"vanishing {perm.name} ({perm.counters[_TIME_COUNTER]} time left)",
            )
    return details
