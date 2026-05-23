"""Apply ability_other ETB hooks when a permanent enters the battlefield."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.other.bloodthirst import apply_bloodthirst_etb
from engine.abilities.keywords.other.living_weapon import (
    apply_living_weapon,
    has_living_weapon,
)
from engine.abilities.keywords.other.modular import apply_modular_etb
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def apply_etb_other_abilities(game: GameState, permanent: Permanent) -> list[str]:
    """Run wired ability_other ETB effects; return log fragments."""
    parts: list[str] = []
    oracle = permanent.oracle_text or ''
    zones = game.zones

    if has_living_weapon(oracle) and 'Equipment' in permanent.type_line:
        parts.append(apply_living_weapon(zones, permanent))

    modular_detail = apply_modular_etb(permanent)
    if modular_detail:
        parts.append(modular_detail)

    bloodthirst_detail = apply_bloodthirst_etb(game, permanent)
    if bloodthirst_detail:
        parts.append(bloodthirst_detail)

    return parts
