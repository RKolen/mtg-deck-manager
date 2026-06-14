"""Fading: enters with fade counters; removed each upkeep; dies at zero."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_FADE_RE = re.compile(r'fading\s+(\w+|\d+)', re.IGNORECASE)
_FADE_COUNTER = 'fade'


def has_fading(perm: Permanent) -> bool:
    """Return True when the permanent has fading."""
    return has_keyword(perm, 'Fading')


def fade_amount(oracle_text: str) -> int:
    """Parse N from 'Fading N'."""
    match = _FADE_RE.search(oracle_text or '')
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_fading_etb(permanent: Permanent) -> str | None:
    """Put fade counters on the permanent when it enters."""
    if not has_fading(permanent):
        return None
    amount = fade_amount(permanent.oracle_text)
    permanent.counters[_FADE_COUNTER] = amount
    return f"fading {permanent.name} ({amount} fade)"


def resolve_fading_upkeep(game: GameState, player_idx: int) -> list[str]:
    """Remove a fade counter from each fading permanent; sacrifice at zero."""
    details: list[str] = []
    for perm in list(game.zones.battlefield):
        if perm.controller_idx != player_idx or not has_fading(perm):
            continue
        fade = perm.counters.get(_FADE_COUNTER, 0)
        if fade <= 0:
            continue
        perm.counters[_FADE_COUNTER] = fade - 1
        if perm.counters[_FADE_COUNTER] <= 0:
            game.zones.leave_battlefield(perm, Zone.GRAVEYARD, 'fading', game)
            details.append(f"fading sacrificed {perm.name}")
        else:
            details.append(f"fading {perm.name} ({perm.counters[_FADE_COUNTER]} left)")
    return details
