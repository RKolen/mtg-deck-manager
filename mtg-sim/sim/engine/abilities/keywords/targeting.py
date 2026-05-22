"""Targeting keywords: Hexproof, Shroud, Ward, Protection."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_PROTECTION_RE = re.compile(r"protection from ([a-z]+)", re.IGNORECASE)
_WARD_COST_RE = re.compile(r"ward\s*(\{[^}]+\})", re.IGNORECASE)
_DEFAULT_WARD_COST = "{2}"
_COLOR_ALIASES = {
    "w": "white",
    "u": "blue",
    "b": "black",
    "r": "red",
    "g": "green",
}


def has_hexproof(perm: Permanent) -> bool:
    """Return True when opponents cannot target this permanent."""
    return has_keyword(perm, 'Hexproof')


def has_shroud(perm: Permanent) -> bool:
    """Return True when no player can target this permanent."""
    return has_keyword(perm, 'Shroud')


def has_ward(perm: Permanent) -> bool:
    """Return True when the permanent has ward."""
    return has_keyword(perm, 'Ward')


def ward_cost(perm: Permanent) -> ManaCost:
    """Return the mana cost an opponent pays to target this permanent with ward."""
    match = _WARD_COST_RE.search(perm.oracle_text)
    if match is None:
        return ManaCost.parse(_DEFAULT_WARD_COST)
    return ManaCost.parse(match.group(1))


def must_pay_ward(source_controller_idx: int, target: Permanent) -> bool:
    """Return True when ward cost applies to this targeting relationship."""
    return has_ward(target) and source_controller_idx != target.controller_idx


def pay_ward_for_target(game: GameState, source_controller_idx: int, target: Permanent) -> bool:
    """Pay ward cost from the spell controller; return False if payment fails."""
    if not must_pay_ward(source_controller_idx, target):
        return True
    return game.players[source_controller_idx].mana_pool.pay(ward_cost(target))


def protection_qualities(perm: Permanent) -> frozenset[str]:
    """Return protection qualities parsed from oracle text (e.g. 'red', 'creatures')."""
    return frozenset(match.group(1).lower() for match in _PROTECTION_RE.finditer(perm.oracle_text))


def has_protection_from(
    perm: Permanent,
    *,
    source_is_creature: bool = False,
    source_colors: frozenset[str] | None = None,
) -> bool:
    """Return True when protection prevents interaction from the described source."""
    qualities = protection_qualities(perm)
    if not qualities and has_keyword(perm, 'Protection'):
        qualities = frozenset({'all'})
    if not qualities:
        return False
    if 'all' in qualities:
        return True
    if source_is_creature and 'creatures' in qualities:
        return True
    if source_colors:
        normalized = {_normalize_protection_color(color) for color in source_colors}
        if qualities.intersection(normalized):
            return True
    return False


def can_target_permanent(
    target: Permanent,
    controller_idx: int,
    *,
    source_is_creature: bool = False,
    source_colors: frozenset[str] | None = None,
) -> bool:
    """Return True when controller_idx may target target with a spell or ability."""
    if has_shroud(target):
        return False
    if has_hexproof(target) and controller_idx != target.controller_idx:
        return False
    if has_protection_from(
        target,
        source_is_creature=source_is_creature,
        source_colors=source_colors,
    ):
        return False
    return True


def _normalize_protection_color(color: str) -> str:
    """Map mana letters and color names to protection quality strings."""
    lowered = color.lower()
    if len(lowered) == 1 and lowered in _COLOR_ALIASES:
        return _COLOR_ALIASES[lowered]
    return lowered
