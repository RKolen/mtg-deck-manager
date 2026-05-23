"""Fight keyword action."""

from __future__ import annotations

from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.core.game_object import Permanent, effective_power


def has_fight(oracle_text: str | None) -> bool:
    """Return True when oracle text contains the Fight action."""
    return has_keyword_action(oracle_text, 'Fight')


def combat_power(perm: Permanent) -> int:
    """Return effective power for fight damage (printed P/T plus +1/+1)."""
    return effective_power(perm)


def fight_creatures(creature_a: Permanent, creature_b: Permanent) -> tuple[int, int]:
    """Each creature deals damage equal to its power to the other. Returns (dmg_a, dmg_b)."""
    power_a = combat_power(creature_a)
    power_b = combat_power(creature_b)
    creature_a.damage_marked += power_b
    creature_b.damage_marked += power_a
    return power_a, power_b
