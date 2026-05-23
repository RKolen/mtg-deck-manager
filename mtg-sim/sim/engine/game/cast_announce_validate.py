"""Validate optional costs when announcing a cast from hand."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords.casting.bestow import (
    bestow_host_error,
    normalize_bestow,
)
from engine.abilities.keywords.casting.buyback import normalize_buyback
from engine.abilities.keywords.casting.emerge import (
    emerge_sacrifice_error,
    normalize_emerge_cast,
    normalize_emerge_sacrifice_id,
)
from engine.abilities.keywords.casting.evoke import normalize_evoke_cast
from engine.abilities.keywords.casting.entwine import normalize_entwined
from engine.abilities.keywords.casting.freerunning import normalize_freerunning_cast
from engine.abilities.keywords.casting.kicker import normalize_kicker_times
from engine.abilities.keywords.casting.miracle import normalize_miracle_cast
from engine.abilities.keywords.casting.mutate import (
    mutate_host_error,
    normalize_mutate_cast,
)
from engine.abilities.keywords.casting.overload import normalize_overloaded
from engine.abilities.keywords.casting.replicate import normalize_replicate_times
from engine.abilities.keywords.casting.spree import (
    normalize_spree_modes,
    spree_selection_error,
)
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager
from engine.game.helpers import CastAnnounceOptions


@dataclass(frozen=True)
class PaidCastModifiers:
    """Normalized optional cost flags after validation."""

    kicker_times: int
    entwined: bool
    overloaded: bool
    bestow: bool
    miracle: bool
    freerunning: bool
    replicate_times: int
    buyback: bool
    emerge: bool
    evoke: bool
    mutate: bool
    spree_modes: tuple[int, ...]


@dataclass(frozen=True)
class PaidAnnounceCast:
    """Paid optional costs and targeting for a hand cast."""

    modifiers: PaidCastModifiers
    emerge_sacrifice_id: int | None
    cast_target_uid: str | None


@dataclass(frozen=True)
class HandCastPlacement:
    """Validated hand cast ready for mana payment and stack placement."""

    card: CardObject
    card_info: CardInfo
    paid: PaidAnnounceCast
    opts: CastAnnounceOptions
    hand_idx: int
    target_player_idx: int | None
    mana_needed: int
    life_cost: int
    auto_resolve: bool


def _reject_keyword(requested: bool, valid: bool, card_name: str, keyword: str) -> str | None:
    if requested and not valid:
        return f"{card_name} does not have {keyword}"
    return None


def _first_error(checks: list[Callable[[], str | None]]) -> str | None:
    for check in checks:
        err = check()
        if err:
            return err
    return None


def _normalized_paid_flags(
    card_info: CardInfo,
    opts: CastAnnounceOptions,
    combat_damage_dealt: bool,
) -> PaidCastModifiers:
    return PaidCastModifiers(
        kicker_times=normalize_kicker_times(card_info, opts.costs.kicker_times),
        entwined=normalize_entwined(card_info, opts.costs.entwined),
        overloaded=normalize_overloaded(card_info, opts.costs.overloaded),
        bestow=normalize_bestow(card_info, opts.modifiers.targeting.bestow_target_uid),
        miracle=normalize_miracle_cast(card_info, opts.alternate.cast_for_miracle),
        freerunning=normalize_freerunning_cast(
            card_info,
            opts.alternate.cast_for_freerunning,
            combat_damage_dealt,
        ),
        replicate_times=normalize_replicate_times(card_info, opts.costs.replicate_times),
        buyback=normalize_buyback(card_info, opts.costs.paid_buyback),
        emerge=normalize_emerge_cast(card_info, opts.alternate.cast_for_emerge),
        evoke=normalize_evoke_cast(card_info, opts.alternate.cast_for_evoke),
        mutate=normalize_mutate_cast(
            card_info,
            opts.alternate.cast_for_mutate,
            opts.modifiers.targeting.mutate_target_uid,
        ),
        spree_modes=normalize_spree_modes(
            card_info,
            list(opts.modifiers.targeting.spree_mode_indices),
        ),
    )


def validate_announce_cast(
    zones: ZoneManager,
    player_idx: int,
    card_info: CardInfo,
    opts: CastAnnounceOptions,
    combat_damage_dealt: bool,
    target_uid_str: str | None,
) -> tuple[PaidAnnounceCast | None, str | None]:
    """Return paid cast options, or (None, error_message) when invalid."""
    name = card_info.name
    paid = _normalized_paid_flags(card_info, opts, combat_damage_dealt)

    err = _first_error([
        lambda: _reject_keyword(
            opts.costs.kicker_times > 0,
            paid.kicker_times > 0,
            name,
            "kicker",
        ),
        lambda: _reject_keyword(opts.costs.entwined, paid.entwined, name, "entwine"),
        lambda: _reject_keyword(opts.costs.overloaded, paid.overloaded, name, "overload"),
        lambda: _reject_keyword(
            bool(opts.modifiers.targeting.bestow_target_uid),
            paid.bestow,
            name,
            "bestow",
        ),
        lambda: bestow_host_error(
            zones,
            player_idx,
            opts.modifiers.targeting.bestow_target_uid,
        ),
        lambda: _reject_keyword(opts.alternate.cast_for_miracle, paid.miracle, name, "miracle"),
        lambda: (
            f"{name} cannot use freerunning"
            if opts.alternate.cast_for_freerunning and not paid.freerunning
            else None
        ),
        lambda: _reject_keyword(
            opts.costs.replicate_times > 0,
            paid.replicate_times > 0,
            name,
            "replicate",
        ),
        lambda: _reject_keyword(opts.costs.paid_buyback, paid.buyback, name, "buyback"),
        lambda: _reject_keyword(opts.alternate.cast_for_emerge, paid.emerge, name, "emerge"),
        lambda: _reject_keyword(opts.alternate.cast_for_evoke, paid.evoke, name, "evoke"),
        lambda: emerge_sacrifice_error(
            zones,
            player_idx,
            card_info,
            opts.alternate.cast_for_emerge,
            list(opts.modifiers.targeting.emerge_sacrifice_ids),
        ),
        lambda: _reject_keyword(opts.alternate.cast_for_mutate, paid.mutate, name, "mutate"),
        lambda: mutate_host_error(
            zones,
            player_idx,
            card_info,
            opts.modifiers.targeting.mutate_target_uid,
        ),
        lambda: spree_selection_error(
            card_info,
            list(opts.modifiers.targeting.spree_mode_indices),
        ),
    ])
    if err:
        return None, err

    emerge_sacrifice_id = normalize_emerge_sacrifice_id(
        card_info,
        opts.alternate.cast_for_emerge,
        list(opts.modifiers.targeting.emerge_sacrifice_ids),
    )
    cast_target_uid = (
        opts.modifiers.targeting.mutate_target_uid
        or opts.modifiers.targeting.bestow_target_uid
        or target_uid_str
    )
    return PaidAnnounceCast(
        modifiers=paid,
        emerge_sacrifice_id=emerge_sacrifice_id,
        cast_target_uid=cast_target_uid,
    ), None
