"""Apply ability_other ETB hooks when a permanent enters the battlefield."""

from __future__ import annotations

from engine.abilities.keywords.other.living_weapon import (
    apply_living_weapon,
    has_living_weapon,
)
from engine.core.game_object import Permanent
from engine.core.zones import ZoneManager


def apply_etb_other_abilities(zones: ZoneManager, permanent: Permanent) -> list[str]:
    """Run wired ability_other ETB effects; return log fragments."""
    parts: list[str] = []
    oracle = permanent.oracle_text or ''
    if has_living_weapon(oracle) and 'Equipment' in permanent.type_line:
        parts.append(apply_living_weapon(zones, permanent))
    return parts
