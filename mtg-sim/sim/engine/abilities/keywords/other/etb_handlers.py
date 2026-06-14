"""ETB detail producers for ability_other keywords."""

from __future__ import annotations

from collections.abc import Callable

from engine.abilities.keywords.other.ascend import update_ascend_status
from engine.abilities.keywords.other.amplify import apply_amplify_etb
from engine.abilities.keywords.other.augment import apply_augment_etb
from engine.abilities.keywords.other.backup import apply_backup_etb
from engine.abilities.keywords.other.blitz import apply_blitz_etb
from engine.abilities.keywords.other.bloodthirst import apply_bloodthirst_etb
from engine.abilities.keywords.other.dash import apply_dash_etb
from engine.abilities.keywords.other.decayed import apply_decayed_etb
from engine.abilities.keywords.other.devour import apply_devour_etb
from engine.abilities.keywords.other.echo import apply_echo_etb
from engine.abilities.keywords.other.fading import apply_fading_etb
from engine.abilities.keywords.other.cumulative_upkeep import apply_cumulative_upkeep_etb
from engine.abilities.keywords.other.encore import apply_encore_etb
from engine.abilities.keywords.other.evoke import apply_evoke_on_etb
from engine.abilities.keywords.other.fabricate import apply_fabricate_etb
from engine.abilities.keywords.other.fortify import apply_fortify_etb
from engine.abilities.keywords.other.graft import apply_graft_etb
from engine.abilities.keywords.other.champion import apply_champion_etb
from engine.abilities.keywords.other.hideaway import apply_hideaway_etb
from engine.abilities.keywords.other.living_weapon import (
    apply_living_weapon,
    has_living_weapon,
)
from engine.abilities.keywords.other.modular import apply_modular_etb
from engine.abilities.keywords.other.offspring import apply_offspring_etb
from engine.abilities.keywords.other.riot import apply_riot_etb
from engine.core.game_object import Permanent
from engine.core.game_state import GameState

EtbDetailFn = Callable[[GameState, Permanent], str | None]


def _living_weapon_detail(game: GameState, permanent: Permanent) -> str | None:
    oracle = permanent.oracle_text or ''
    if has_living_weapon(oracle) and 'Equipment' in permanent.type_line:
        return apply_living_weapon(game.zones, permanent)
    return None


def _modular_detail(_game: GameState, permanent: Permanent) -> str | None:
    return apply_modular_etb(permanent)


def _bloodthirst_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_bloodthirst_etb(game, permanent)


def _fabricate_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_fabricate_etb(game.zones, permanent)


def _devour_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_devour_etb(game, permanent)


def _dash_detail(_game: GameState, permanent: Permanent) -> str | None:
    return apply_dash_etb(permanent)


def _blitz_detail(_game: GameState, permanent: Permanent) -> str | None:
    return apply_blitz_etb(permanent)


def _backup_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_backup_etb(permanent, game.zones.battlefield)


def _echo_detail(_game: GameState, permanent: Permanent) -> str | None:
    return apply_echo_etb(permanent)


def _fading_detail(_game: GameState, permanent: Permanent) -> str | None:
    return apply_fading_etb(permanent)


def _cumulative_upkeep_detail(_game: GameState, permanent: Permanent) -> str | None:
    return apply_cumulative_upkeep_etb(permanent)


def _augment_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_augment_etb(game.zones, permanent, game.zones.battlefield)


def _riot_detail(_game: GameState, permanent: Permanent) -> str | None:
    return apply_riot_etb(permanent)


def _encore_detail(_game: GameState, permanent: Permanent) -> str | None:
    return apply_encore_etb(permanent)


def _ascend_detail(game: GameState, permanent: Permanent) -> str | None:
    return update_ascend_status(game, permanent.controller_idx)


def _evoke_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_evoke_on_etb(game, permanent)


def _offspring_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_offspring_etb(game.zones, permanent)


def _decayed_detail(_game: GameState, permanent: Permanent) -> str | None:
    return apply_decayed_etb(permanent)


def _graft_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_graft_etb(game, permanent)


def _amplify_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_amplify_etb(game, permanent)


def _champion_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_champion_etb(game, permanent)


def _hideaway_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_hideaway_etb(game, permanent)


def _fortify_detail(game: GameState, permanent: Permanent) -> str | None:
    return apply_fortify_etb(game, permanent)


ETB_DETAIL_PRODUCERS: tuple[EtbDetailFn, ...] = (
    _living_weapon_detail,
    _modular_detail,
    _bloodthirst_detail,
    _fabricate_detail,
    _devour_detail,
    _dash_detail,
    _blitz_detail,
    _backup_detail,
    _echo_detail,
    _fading_detail,
    _cumulative_upkeep_detail,
    _augment_detail,
    _riot_detail,
    _encore_detail,
    _ascend_detail,
    _evoke_detail,
    _offspring_detail,
    _decayed_detail,
    _graft_detail,
    _amplify_detail,
    _champion_detail,
    _hideaway_detail,
    _fortify_detail,
)
