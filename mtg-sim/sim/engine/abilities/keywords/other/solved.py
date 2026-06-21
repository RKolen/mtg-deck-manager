"""Solved and To solve: Case enchantment designations (CR 702.169, 719.3)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_TO_SOLVE_RE = re.compile(
    r'to solve\s*[—–-]\s*([^\n]+)',
    re.IGNORECASE,
)
_SOLVED_RE = re.compile(
    r'solved\s*[—–-]\s*([^\n]+)',
    re.IGNORECASE,
)
_SOLVED_COUNTER = 'solved'


def has_to_solve(perm: Permanent) -> bool:
    """Return True when the permanent has a to solve ability."""
    text = perm.oracle_text or ''
    return has_registered_keyword(text, 'To solve') or bool(_TO_SOLVE_RE.search(text))


def has_solved_ability(perm: Permanent) -> bool:
    """Return True when the permanent has a solved ability line."""
    text = perm.oracle_text or ''
    return has_registered_keyword(text, 'Solved') or bool(_SOLVED_RE.search(text))


def is_solved(perm: Permanent) -> bool:
    """Return True when the Case has the solved designation."""
    return perm.counters.get(_SOLVED_COUNTER, 0) > 0


def mark_solved(perm: Permanent) -> str:
    """Mark a Case as solved."""
    perm.counters[_SOLVED_COUNTER] = 1
    return f"solved {perm.name}"


def _count_subtype_creatures(game: GameState, controller_idx: int, subtype: str) -> int:
    needle = subtype.lower()
    return sum(
        1
        for perm in game.zones.battlefield
        if perm.controller_idx == controller_idx
        and 'Creature' in perm.type_line
        and needle in perm.type_line.lower()
    )


def _count_creatures(game: GameState, controller_idx: int) -> int:
    return sum(
        1
        for perm in game.zones.battlefield
        if perm.controller_idx == controller_idx and 'Creature' in perm.type_line
    )


def _count_lands(game: GameState, controller_idx: int) -> int:
    return sum(
        1
        for perm in game.zones.battlefield
        if perm.controller_idx == controller_idx and 'Land' in perm.type_line
    )


def to_solve_condition_met(game: GameState, perm: Permanent) -> bool:
    """Return True when a simplified to solve condition is met."""
    match = _TO_SOLVE_RE.search(perm.oracle_text or '')
    if match is None:
        return False
    condition = match.group(1).lower()
    controller_idx = perm.controller_idx
    if 'three or more detectives' in condition:
        return _count_subtype_creatures(game, controller_idx, 'Detective') >= 3
    if 'three or more creatures' in condition:
        return _count_creatures(game, controller_idx) >= 3
    if 'seven or more lands' in condition or 'seven lands' in condition:
        return _count_lands(game, controller_idx) >= 7
    if 'four or more creatures' in condition:
        return _count_creatures(game, controller_idx) >= 4
    return False


def resolve_to_solve_end_step(game: GameState, player_idx: int) -> list[str]:
    """Solve Cases whose to solve conditions are met at end step."""
    details: list[str] = []
    for perm in game.zones.battlefield:
        if perm.controller_idx != player_idx or is_solved(perm):
            continue
        if not has_to_solve(perm):
            continue
        if not to_solve_condition_met(game, perm):
            continue
        details.append(mark_solved(perm))
    return details


def solved_grants_keyword(perm: Permanent, keyword: str) -> bool:
    """Return True when a solved Case grants a static keyword."""
    if not is_solved(perm) or not has_solved_ability(perm):
        return False
    match = _SOLVED_RE.search(perm.oracle_text or '')
    if match is None:
        return False
    return keyword.lower() in match.group(1).lower()


def has_case_keyword(perm: Permanent) -> bool:
    """Return True when the permanent is a Case enchantment."""
    return 'Case' in perm.type_line or has_to_solve(perm) or has_solved_ability(perm)
