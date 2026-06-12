"""Echo: pay echo cost at upkeep or sacrifice (CR 702.29, simplified)."""

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

_ECHO_COST_RE = re.compile(
    r'echo\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_ECHO_COUNTER = 'echo'
_ECHO_MANA_COUNTER = 'echo_mana'


def has_echo(perm: Permanent) -> bool:
    """Return True when the permanent has echo."""
    return has_keyword(perm, 'Echo')


def echo_cost(oracle_text: str) -> ManaCost | None:
    """Parse echo cost from oracle text."""
    match = _ECHO_COST_RE.search(oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def echo_mana_needed(oracle_text: str) -> int:
    """Return generic mana needed to pay echo."""
    cost = echo_cost(oracle_text)
    return cost.mana_value if cost is not None else 2


def apply_echo_etb(permanent: Permanent) -> str | None:
    """Mark a creature that will owe echo at the next upkeep."""
    if not has_echo(permanent):
        return None
    permanent.counters[_ECHO_COUNTER] = 1
    permanent.counters[_ECHO_MANA_COUNTER] = echo_mana_needed(permanent.oracle_text)
    return f"{permanent.name} owes echo"


def resolve_echo_upkeep(
    game: GameState,
    player_idx: int,
    tap_mana: Callable[[int, int], bool],
) -> list[str]:
    """Pay echo costs or sacrifice echo creatures at upkeep."""
    details: list[str] = []
    for perm in list(game.zones.battlefield):
        if perm.controller_idx != player_idx:
            continue
        if not perm.counters.get(_ECHO_COUNTER):
            continue
        mana = int(perm.counters.get(_ECHO_MANA_COUNTER, 0))
        if mana > 0 and tap_mana(player_idx, mana):
            perm.counters.pop(_ECHO_COUNTER, None)
            perm.counters.pop(_ECHO_MANA_COUNTER, None)
            details.append(f"paid echo for {perm.name}")
            continue
        if perm in game.zones.battlefield:
            game.zones.leave_battlefield(perm, Zone.GRAVEYARD, 'echo')
            details.append(f"sacrificed {perm.name} (echo)")
    return details
