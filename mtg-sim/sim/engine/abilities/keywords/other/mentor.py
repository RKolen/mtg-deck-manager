"""Mentor: when this attacks, put +1/+1 on an attacking creature with lesser power."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent, effective_power

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_mentor(perm: Permanent) -> bool:
    """Return True when the permanent has mentor."""
    return has_keyword(perm, 'Mentor')


def apply_mentor_on_attack(
    game: GameState,
    mentor: Permanent,
    attacker_ids: list[str],
) -> str | None:
    """Put a +1/+1 counter on another attacking creature with less power."""
    if not has_mentor(mentor):
        return None
    mentor_power = effective_power(mentor)
    best: Permanent | None = None
    best_power = -1
    for attacker_id in attacker_ids:
        if attacker_id == str(mentor.obj_id):
            continue
        perm = game.zones.find_permanent(int(attacker_id))
        if perm is None or perm.controller_idx != mentor.controller_idx:
            continue
        power = effective_power(perm)
        if power >= mentor_power:
            continue
        if best is None or power > best_power:
            best = perm
            best_power = power
    if best is None:
        return None
    put_plus_counters(best, 1)
    return f"mentor +1/+1 on {best.name}"
