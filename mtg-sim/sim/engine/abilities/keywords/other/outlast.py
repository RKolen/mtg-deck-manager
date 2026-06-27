"""Outlast: pay cost to put a +1/+1 counter on this creature (once per turn)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent
from engine.core.game_state import GameState
from engine.core.mana import ManaCost

_OUTLAST_RE = re.compile(
    r'outlast\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_OUTLAST_USED = 'outlast_used'


def has_outlast(perm: Permanent) -> bool:
    """Return True when the permanent has outlast."""
    return has_registered_keyword(perm.oracle_text, 'Outlast') or bool(
        _OUTLAST_RE.search(perm.oracle_text or '')
    )


def has_outlast_card(card: CardInfo) -> bool:
    """Return True when the card has outlast."""
    return has_registered_keyword(card.oracle_text, 'Outlast') or bool(
        _OUTLAST_RE.search(card.oracle_text or '')
    )


def outlast_cost(perm: Permanent) -> ManaCost | None:
    """Parse the outlast activation cost from oracle text."""
    match = _OUTLAST_RE.search(perm.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def outlast_mana_needed(perm: Permanent) -> int:
    """Return generic mana to activate outlast."""
    cost = outlast_cost(perm)
    if cost is None:
        return 0
    return cost.mana_value


def can_outlast(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when outlast may be activated."""
    if not has_outlast(perm) or perm.controller_idx != controller_idx:
        return False
    if perm.counters.get(_OUTLAST_USED):
        return False
    return phase in ('main1', 'main2') and game.stack.is_empty


def apply_outlast(perm: Permanent) -> str | None:
    """Put a +1/+1 counter on this creature after outlast is paid."""
    if not has_outlast(perm):
        return None
    put_plus_counters(perm, 1)
    perm.counters[_OUTLAST_USED] = 1
    return f"outlast +1/+1 on {perm.name}"


def clear_outlast_turn_marker(perm: Permanent) -> None:
    """Clear the once-per-turn outlast marker."""
    perm.counters.pop(_OUTLAST_USED, None)
