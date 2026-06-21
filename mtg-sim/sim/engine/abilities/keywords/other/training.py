"""Training: +1/+1 when a creature with greater power attacks with this."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import Permanent, effective_power

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_training(perm: Permanent) -> bool:
    """Return True when the permanent has training."""
    return has_keyword(perm, 'Training')


def apply_training_on_attack(
    game: GameState,
    trainee: Permanent,
    attacker_ids: list[str],
) -> str | None:
    """Put a +1/+1 counter on this creature when a stronger ally attacks."""
    if not has_training(trainee):
        return None
    trainee_power = effective_power(trainee)
    for attacker_id in attacker_ids:
        if attacker_id == str(trainee.obj_id):
            continue
        perm = game.zones.find_permanent(int(attacker_id))
        if perm is None or perm.controller_idx != trainee.controller_idx:
            continue
        if effective_power(perm) > trainee_power:
            put_plus_counters(trainee, 1)
            return f"training +1/+1 on {trainee.name}"
    return None
