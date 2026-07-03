"""Fight keyword action."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.core.game_object import Permanent, effective_power

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_fight(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Fight action."""
    return has_keyword_action(oracle_text, 'Fight')


def combat_power(perm: Permanent, game: GameState | None = None) -> int:
    """Return effective power for fight damage."""
    return effective_power(perm, game)


def fight_creatures(
    creature_a: Permanent,
    creature_b: Permanent,
    game: GameState | None = None,
) -> tuple[int, int]:
    """Each creature deals damage equal to its power to the other. Returns (dmg_a, dmg_b)."""
    power_a = combat_power(creature_a, game)
    power_b = combat_power(creature_b, game)
    creature_a.damage_marked += power_b
    creature_b.damage_marked += power_a
    return power_a, power_b
