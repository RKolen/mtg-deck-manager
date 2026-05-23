"""Apply ability_other ETB hooks when a permanent enters the battlefield."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.other.ascend import update_ascend_status
from engine.abilities.keywords.other.backup import apply_backup_etb
from engine.abilities.keywords.other.blitz import apply_blitz_etb
from engine.abilities.keywords.other.bloodthirst import apply_bloodthirst_etb
from engine.abilities.keywords.other.dash import apply_dash_etb
from engine.abilities.keywords.other.devour import apply_devour_etb
from engine.abilities.keywords.other.embalm import apply_embalm_etb
from engine.abilities.keywords.other.evoke import apply_evoke_on_etb
from engine.abilities.keywords.other.fabricate import apply_fabricate_etb
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

    fabricate_detail = apply_fabricate_etb(zones, permanent)
    if fabricate_detail:
        parts.append(fabricate_detail)

    devour_detail = apply_devour_etb(game, permanent)
    if devour_detail:
        parts.append(devour_detail)

    dash_detail = apply_dash_etb(permanent)
    if dash_detail:
        parts.append(dash_detail)

    blitz_detail = apply_blitz_etb(permanent)
    if blitz_detail:
        parts.append(blitz_detail)

    backup_detail = apply_backup_etb(permanent, zones.battlefield)
    if backup_detail:
        parts.append(backup_detail)

    embalm_detail = apply_embalm_etb(zones, permanent)
    if embalm_detail:
        parts.append(embalm_detail)

    ascend_detail = update_ascend_status(game, permanent.controller_idx)
    if ascend_detail:
        parts.append(ascend_detail)

    evoke_detail = apply_evoke_on_etb(game, permanent)
    if evoke_detail:
        parts.append(evoke_detail)

    return parts
