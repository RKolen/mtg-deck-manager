"""Station: tap creatures to animate a Spacecraft (simplified)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent, effective_power

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_STATION_RE = re.compile(r'station\s*(\d+)', re.IGNORECASE)
_CREWED_COUNTER = 'crewed'


def has_station(perm: Permanent) -> bool:
    """Return True when the permanent has station."""
    oracle = perm.oracle_text or ''
    return (
        'Spacecraft' in perm.type_line
        or has_registered_keyword(oracle, 'Station')
        or bool(_STATION_RE.search(oracle))
    )


def station_cost(perm: Permanent) -> int:
    """Return the station number from oracle text."""
    match = _STATION_RE.search(perm.oracle_text or '')
    if match is None:
        return 0
    return int(match.group(1))


def is_stationed(perm: Permanent) -> bool:
    """Return True when a spacecraft has been stationed this turn."""
    return has_station(perm) and perm.counters.get(_CREWED_COUNTER, 0) > 0


def can_station(
    spacecraft: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when the spacecraft may be stationed now."""
    if not has_station(spacecraft) or spacecraft.controller_idx != controller_idx:
        return False
    if phase not in ('main1', 'main2') or not game.stack.is_empty:
        return False
    return not spacecraft.tapped


def _find_perm(game: GameState, uid: str) -> Permanent | None:
    for perm in game.zones.battlefield:
        if str(perm.obj_id) == uid:
            return perm
    return None


def station_power_error(  # pylint: disable=too-many-return-statements
    game: GameState,
    controller_idx: int,
    crewer_ids: list[str],
    required: int,
) -> str | None:
    """Return an error when tapped creatures do not meet the station requirement."""
    if required <= 0:
        return 'Invalid station cost'
    total = 0
    for uid in crewer_ids:
        perm = _find_perm(game, uid)
        if perm is None:
            return f'Crewer {uid} not found'
        if perm.controller_idx != controller_idx:
            return f'{perm.name} cannot station'
        if 'Creature' not in perm.type_line:
            return f'{perm.name} is not a creature'
        if perm.tapped:
            return f'{perm.name} is already tapped'
        total += effective_power(perm)
    if total < required:
        return f'Need station power {required}, have {total}'
    return None


def apply_station(
    game: GameState,
    spacecraft: Permanent,
    crewer_ids: list[str],
) -> None:
    """Tap creatures and mark the spacecraft as stationed."""
    required = station_cost(spacecraft) or 1
    for uid in crewer_ids:
        perm = _find_perm(game, uid)
        assert perm is not None
        perm.tapped = True
    spacecraft.counters[_CREWED_COUNTER] = required
    spacecraft.sick = False
