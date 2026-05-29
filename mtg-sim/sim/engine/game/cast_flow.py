"""Shared announce-cast helpers (mana options, cost tuples, client errors)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from deck_registry import CardInfo
from engine.core.game_object import CardObject, SpellAlternateCast
from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaModifiers,
    CastManaTiming,
)
from engine.abilities.keywords.casting.spectacle import spectacle_available
from engine.core.game_state import GameState
from engine.game.cast_announce_validate import PaidAnnounceCast
from engine.game.cast_context import CastAnnounceOptions, SpellCastContext
from engine.game.face_alternate_cast import FaceAlternateCastFlags

ManaAndLife: TypeAlias = tuple[int, int]
ManaCostFn: TypeAlias = Callable[[CardInfo], int | ManaAndLife]


@dataclass(frozen=True)
class AnnounceCastCompletion:
    """Arguments for finishing an announce cast after costs are paid."""

    card: CardObject
    card_info: CardInfo
    player_idx: int
    target_uid_str: str | None
    target_player_idx: int | None
    context: SpellCastContext
    log_action: str
    log_detail: str
    auto_resolve: bool
    life_cost: int = 0


@dataclass(frozen=True)
class ExileCastRequest:
    """Options for casting a spell from exile (foretell, plot)."""

    card: CardObject
    card_info: CardInfo
    target_uid_str: str | None
    target_player_idx: int | None
    auto_resolve: bool
    alternate: SpellAlternateCast
    log_detail: str
    life_cost: int = 0


@dataclass(frozen=True)
class GraveyardCastRequest:
    """Keyword-specific options for casting from the graveyard."""

    player_idx: int
    has_keyword: Callable[[CardInfo], bool]
    keyword_error: Callable[[CardInfo], str]
    can_cast: Callable[[CardInfo], bool]
    timing_error: str
    mana_cost: ManaCostFn
    alternate: SpellAlternateCast
    log_action: str
    log_detail: Callable[[CardInfo], str] | str
    prepay: Callable[[CardObject, CardInfo], str | None] | None = None


def split_mana_cost(cost: int | ManaAndLife) -> ManaAndLife:
    """Normalize a mana cost as either an int or (mana, life) tuple."""
    if isinstance(cost, tuple):
        return cost
    return cost, 0


def not_enough_mana_message(available: int, needed: int) -> str:
    """Build the standard insufficient-mana error string."""
    return f"Not enough mana ({available} available, need {needed})"


def cast_modifiers_for_announce(
    paid: PaidAnnounceCast,
    opts: CastAnnounceOptions,
) -> CastManaModifiers:
    """Build CastManaModifiers from validated announce state and request options."""
    return CastManaModifiers(
        kicker_times=paid.modifiers.kicker_times,
        entwined=paid.modifiers.entwined,
        overloaded=paid.modifiers.overloaded,
        bestow_target_uid=opts.modifiers.targeting.bestow_target_uid,
        replicate_times=paid.modifiers.replicate_times,
        paid_buyback=paid.modifiers.buyback,
        cast_for_emerge=paid.modifiers.emerge,
        cast_for_evoke=paid.modifiers.evoke,
        cast_for_mutate=paid.modifiers.mutate,
        mutate_target_uid=opts.modifiers.targeting.mutate_target_uid,
        spree_mode_indices=paid.modifiers.spree_modes,
        face=FaceAlternateCastFlags(
            cast_for_morph=paid.modifiers.morph,
            cast_for_disguise=paid.modifiers.disguise,
            cast_for_dash=paid.modifiers.dash,
            cast_for_blitz=paid.modifiers.blitz,
        ),
    )


def cast_timing_for_announce(
    paid: PaidAnnounceCast,
    state: GameState,
    controller_idx: int,
) -> CastManaTiming:
    """Build CastManaTiming from validated announce state."""
    return CastManaTiming(
        cast_for_miracle=paid.modifiers.miracle,
        cast_for_freerunning=paid.modifiers.freerunning,
        freerunning_available=state.players[controller_idx].combat_damage_dealt_this_turn,
        cast_for_spectacle=paid.modifiers.spectacle,
        spectacle_available=spectacle_available(state, controller_idx),
        cast_for_morph=paid.modifiers.morph,
    )


def announce_mana_options(
    paid: PaidAnnounceCast,
    opts: CastAnnounceOptions,
    state: GameState,
    controller_idx: int,
) -> AnnounceCastManaOptions:
    """Build announce-cast mana options from validated hand cast state."""
    return AnnounceCastManaOptions(
        modifiers=cast_modifiers_for_announce(paid, opts),
        timing=cast_timing_for_announce(paid, state, controller_idx),
        zones=state.zones,
        controller_idx=controller_idx,
    )
