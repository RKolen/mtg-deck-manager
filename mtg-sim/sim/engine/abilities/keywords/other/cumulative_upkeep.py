"""Cumulative upkeep: pay an increasing cost at upkeep or sacrifice."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_CU_RE = re.compile(r'cumulative upkeep\s*((?:\{[^}]+\})+)', re.IGNORECASE)
_CU_COUNTER = 'cu'
_CU_MANA_COUNTER = 'cu_mana'


def has_cumulative_upkeep(perm: Permanent) -> bool:
    """Return True when the permanent has cumulative upkeep."""
    return has_keyword(perm, 'Cumulative upkeep')


def cumulative_upkeep_cost(oracle_text: str) -> ManaCost | None:
    """Parse the cumulative upkeep cost from oracle text."""
    match = _CU_RE.search(oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def cumulative_upkeep_mana(oracle_text: str) -> int:
    """Return generic mana for one cumulative upkeep payment."""
    cost = cumulative_upkeep_cost(oracle_text)
    return cost.mana_value if cost is not None else 1


def apply_cumulative_upkeep_etb(permanent: Permanent) -> str | None:
    """Mark cumulative upkeep owed at the next upkeep."""
    if not has_cumulative_upkeep(permanent):
        return None
    permanent.counters[_CU_COUNTER] = 1
    permanent.counters[_CU_MANA_COUNTER] = cumulative_upkeep_mana(permanent.oracle_text)
    return f"{permanent.name} owes cumulative upkeep"


def resolve_cumulative_upkeep(
    game: GameState,
    player_idx: int,
    tap_mana: Callable[[int, int], bool],
) -> list[str]:
    """Pay cumulative upkeep or sacrifice each owing permanent."""
    details: list[str] = []
    for perm in list(game.zones.battlefield):
        if perm.controller_idx != player_idx or not perm.counters.get(_CU_COUNTER):
            continue
        mana = perm.counters.get(_CU_MANA_COUNTER, 1)
        if tap_mana(player_idx, mana):
            perm.counters[_CU_MANA_COUNTER] = mana + cumulative_upkeep_mana(perm.oracle_text)
            details.append(f"paid cumulative upkeep on {perm.name}")
            continue
        game.zones.leave_battlefield(perm, Zone.GRAVEYARD, 'cumulative_upkeep', game)
        details.append(f"cumulative upkeep sacrificed {perm.name}")
    return details
