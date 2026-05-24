"""Boast: activated only during combat while attacking, once per turn."""

from __future__ import annotations

import re
from collections.abc import Callable

from engine.abilities.activated.core import activation_mana_value
from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

_BOAST_RE = re.compile(
    r'((?:\{[^}]+\})+)\s*:\s*Boast\s*[—–-]',
    re.IGNORECASE,
)
_ATTACKED_COUNTER = 'attacked_this_turn'
_BOASTED_COUNTER = 'boasted_this_turn'


def has_boast(perm: Permanent) -> bool:
    """Return True when the permanent has a boast activated ability."""
    return has_keyword(perm, 'Boast') and _BOAST_RE.search(perm.oracle_text or '') is not None


def boast_mana_needed(perm: Permanent) -> int:
    """Return generic mana to activate boast (simplified)."""
    match = _BOAST_RE.search(perm.oracle_text or '')
    if match is None:
        return 0
    return activation_mana_value(match.group(1))


def mark_attacked_this_turn(permanent: Permanent) -> None:
    """Mark a creature as having attacked this turn."""
    permanent.counters[_ATTACKED_COUNTER] = 1


def clear_boast_turn_counters(permanent: Permanent) -> None:
    """Clear boast and attacked markers at the start of a new turn."""
    permanent.counters.pop(_ATTACKED_COUNTER, None)
    permanent.counters.pop(_BOASTED_COUNTER, None)


def can_boast(
    perm: Permanent,
    phase: str,
    *,
    is_attacking: bool = False,
) -> bool:
    """Return True when boast may be activated now."""
    if not has_boast(perm):
        return False
    if phase not in ('attack', 'main1', 'main2'):
        return False
    if perm.counters.get(_BOASTED_COUNTER):
        return False
    attacked = perm.counters.get(_ATTACKED_COUNTER) or is_attacking
    return bool(attacked)


def apply_boast(
    perm: Permanent,
    player_idx: int,
    draw_fn: Callable[[int, int], list],
) -> str | None:
    """Pay boast and apply a simplified effect from oracle text."""
    if not has_boast(perm):
        return None
    perm.counters[_BOASTED_COUNTER] = 1
    oracle = (perm.oracle_text or '').lower()
    if 'draw a card' in oracle:
        drawn = draw_fn(player_idx, 1)
        return f"boast {perm.name}, drew {len(drawn)}"
    return f"boasted with {perm.name}"
