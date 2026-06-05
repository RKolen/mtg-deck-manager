"""Validate optional costs when announcing a cast from hand."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from deck_registry import CardInfo
from engine.abilities.keywords.casting.bestow import (
    bestow_host_error,
    normalize_bestow,
)
from engine.abilities.keywords.casting.buyback import normalize_buyback
from engine.abilities.keywords.casting.casualty import (
    casualty_sacrifice_error,
    normalize_casualty_sacrifice_id,
    normalize_paid_casualty,
)
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
from engine.abilities.keywords.casting.spectacle import (
    has_spectacle,
    normalize_spectacle_cast,
    spectacle_available,
)
from engine.abilities.keywords.casting.blitz import normalize_blitz_cast
from engine.abilities.keywords.casting.cleave import normalize_cleave_cast
from engine.abilities.keywords.casting.conspire import (
    conspire_error,
    normalize_paid_conspire,
)
from engine.abilities.keywords.casting.dash import normalize_dash_cast
from engine.abilities.keywords.other.disguise import normalize_disguise_cast
from engine.abilities.keywords.other.morph import normalize_morph_cast
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
from engine.core.game_state import GameState
from engine.core.zones import ZoneManager
from engine.game.helpers import CastAnnounceOptions


@dataclass(frozen=True)
class _FaceCastFlags:
    """Face-down and timing-based alternate cast flags."""

    morph: bool = False
    disguise: bool = False
    dash: bool = False
    blitz: bool = False


@dataclass(frozen=True)
class _SacCastFlags:
    """Sacrifice-based alternate cast flags."""

    emerge: bool = False
    evoke: bool = False
    mutate: bool = False
    casualty: bool = False


@dataclass(frozen=True)
class _ConditionCastFlags:
    """Condition-gated alternate cast flags."""

    miracle: bool = False
    freerunning: bool = False
    spectacle: bool = False


@dataclass(frozen=True)
class _RepeatCostCounts:
    """Repeat-cost integer counts."""

    kicker_times: int = 0
    replicate_times: int = 0


@dataclass(frozen=True)
class _FlatCostFlags:
    """Flat boolean optional cost flags."""

    entwined: bool = False
    overloaded: bool = False
    bestow: bool = False
    buyback: bool = False
    cleave: bool = False
    conspire: bool = False
    counts: _RepeatCostCounts = field(default_factory=_RepeatCostCounts)


@dataclass(frozen=True)
class PaidCastModifiers:
    """Normalized optional cost flags after validation."""

    spree_modes: tuple[int, ...]
    flat: _FlatCostFlags = field(default_factory=_FlatCostFlags)
    face: _FaceCastFlags = field(default_factory=_FaceCastFlags)
    sac: _SacCastFlags = field(default_factory=_SacCastFlags)
    conditions: _ConditionCastFlags = field(default_factory=_ConditionCastFlags)

    @property
    def kicker_times(self) -> int:
        """Number of times kicker was paid."""
        return self.flat.counts.kicker_times

    @property
    def entwined(self) -> bool:
        """Whether entwine was paid."""
        return self.flat.entwined

    @property
    def overloaded(self) -> bool:
        """Whether overload was paid."""
        return self.flat.overloaded

    @property
    def bestow(self) -> bool:
        """Whether bestow was paid."""
        return self.flat.bestow

    @property
    def replicate_times(self) -> int:
        """Number of times replicate was paid."""
        return self.flat.counts.replicate_times

    @property
    def buyback(self) -> bool:
        """Whether buyback was paid."""
        return self.flat.buyback

    @property
    def cleave(self) -> bool:
        """Whether cleave was paid."""
        return self.flat.cleave

    @property
    def conspire(self) -> bool:
        """Whether conspire was paid."""
        return self.flat.conspire

    @property
    def miracle(self) -> bool:
        """Whether miracle was used."""
        return self.conditions.miracle

    @property
    def freerunning(self) -> bool:
        """Whether freerunning was used."""
        return self.conditions.freerunning

    @property
    def spectacle(self) -> bool:
        """Whether spectacle was used."""
        return self.conditions.spectacle

    @property
    def morph(self) -> bool:
        """Whether morph (face-down) was used."""
        return self.face.morph

    @property
    def disguise(self) -> bool:
        """Whether disguise (face-down) was used."""
        return self.face.disguise

    @property
    def dash(self) -> bool:
        """Whether dash was used."""
        return self.face.dash

    @property
    def blitz(self) -> bool:
        """Whether blitz was used."""
        return self.face.blitz

    @property
    def emerge(self) -> bool:
        """Whether emerge was used."""
        return self.sac.emerge

    @property
    def evoke(self) -> bool:
        """Whether evoke was used."""
        return self.sac.evoke

    @property
    def mutate(self) -> bool:
        """Whether mutate was used."""
        return self.sac.mutate

    @property
    def casualty(self) -> bool:
        """Whether casualty was used."""
        return self.sac.casualty


@dataclass(frozen=True)
class PaidAnnounceCast:
    """Paid optional costs and targeting for a hand cast."""

    modifiers: PaidCastModifiers
    emerge_sacrifice_id: int | None
    casualty_sacrifice_id: int | None
    cast_target_uid: str | None


@dataclass(frozen=True)
class _CastManaInfo:
    """Mana and life cost for a cast."""

    mana_needed: int
    life_cost: int


@dataclass(frozen=True)
class _CastPlacementInfo:
    """Card, hand index, and target info for placement."""

    card: CardObject
    hand_idx: int
    target_player_idx: int | None


@dataclass(frozen=True)
class HandCastPlacement:
    """Validated hand cast ready for mana payment and stack placement."""

    placement: _CastPlacementInfo
    card_info: CardInfo
    paid: PaidAnnounceCast
    opts: CastAnnounceOptions
    cost: _CastManaInfo
    auto_resolve: bool

    @property
    def card(self) -> CardObject:
        """The card being cast."""
        return self.placement.card

    @property
    def hand_idx(self) -> int:
        """Hand index of the card."""
        return self.placement.hand_idx

    @property
    def target_player_idx(self) -> int | None:
        """Target player index."""
        return self.placement.target_player_idx

    @property
    def mana_needed(self) -> int:
        """Mana needed for this cast."""
        return self.cost.mana_needed

    @property
    def life_cost(self) -> int:
        """Life cost for this cast."""
        return self.cost.life_cost


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
    game: GameState,
    player_idx: int,
) -> PaidCastModifiers:
    return PaidCastModifiers(
        spree_modes=normalize_spree_modes(
            card_info,
            list(opts.modifiers.targeting.spree_mode_indices),
        ),
        flat=_FlatCostFlags(
            entwined=normalize_entwined(card_info, opts.costs.entwined),
            overloaded=normalize_overloaded(card_info, opts.costs.overloaded),
            bestow=normalize_bestow(card_info, opts.modifiers.targeting.bestow_target_uid),
            buyback=normalize_buyback(card_info, opts.costs.paid_buyback),
            cleave=normalize_cleave_cast(card_info, opts.alternate.cast_for_cleave),
            conspire=normalize_paid_conspire(card_info, opts.costs.paid_conspire),
            counts=_RepeatCostCounts(
                kicker_times=normalize_kicker_times(card_info, opts.costs.kicker_times),
                replicate_times=normalize_replicate_times(card_info, opts.costs.replicate_times),
            ),
        ),
        face=_FaceCastFlags(
            morph=normalize_morph_cast(card_info, opts.alternate.cast_for_morph),
            disguise=normalize_disguise_cast(card_info, opts.alternate.cast_for_disguise),
            dash=normalize_dash_cast(card_info, opts.alternate.cast_for_dash),
            blitz=normalize_blitz_cast(card_info, opts.alternate.cast_for_blitz),
        ),
        sac=_SacCastFlags(
            emerge=normalize_emerge_cast(card_info, opts.alternate.cast_for_emerge),
            evoke=normalize_evoke_cast(card_info, opts.alternate.cast_for_evoke),
            mutate=normalize_mutate_cast(
                card_info,
                opts.alternate.cast_for_mutate,
                opts.modifiers.targeting.mutate_target_uid,
            ),
            casualty=normalize_paid_casualty(card_info, opts.costs.paid_casualty),
        ),
        conditions=_ConditionCastFlags(
            miracle=normalize_miracle_cast(card_info, opts.alternate.cast_for_miracle),
            freerunning=normalize_freerunning_cast(
                card_info,
                opts.alternate.cast_for_freerunning,
                combat_damage_dealt,
            ),
            spectacle=normalize_spectacle_cast(
                card_info,
                opts.alternate.cast_for_spectacle,
                available=spectacle_available(game, player_idx),
            ),
        ),
    )


@dataclass(frozen=True)
class _CastValidationContext:
    """Game context for cast validation."""

    zones: ZoneManager
    game: GameState
    player_idx: int


def validate_announce_cast(
    ctx: _CastValidationContext,
    card_info: CardInfo,
    opts: CastAnnounceOptions,
    combat_damage_dealt: bool,
    target_uid_str: str | None,
) -> tuple[PaidAnnounceCast | None, str | None]:
    """Return paid cast options, or (None, error_message) when invalid."""
    name = card_info.name
    paid = _normalized_paid_flags(card_info, opts, combat_damage_dealt, ctx.game, ctx.player_idx)

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
            ctx.zones,
            ctx.player_idx,
            opts.modifiers.targeting.bestow_target_uid,
        ),
        lambda: _reject_keyword(opts.alternate.cast_for_miracle, paid.miracle, name, "miracle"),
        lambda: _reject_keyword(
            opts.alternate.cast_for_spectacle,
            paid.spectacle,
            name,
            "spectacle",
        ),
        lambda: (
            "Spectacle requires an opponent to have lost life this turn"
            if opts.alternate.cast_for_spectacle
            and has_spectacle(card_info)
            and not spectacle_available(ctx.game, ctx.player_idx)
            else None
        ),
        lambda: _reject_keyword(opts.alternate.cast_for_morph, paid.morph, name, "morph"),
        lambda: _reject_keyword(opts.alternate.cast_for_disguise, paid.disguise, name, "disguise"),
        lambda: _reject_keyword(opts.alternate.cast_for_dash, paid.dash, name, "dash"),
        lambda: _reject_keyword(opts.alternate.cast_for_blitz, paid.blitz, name, "blitz"),
        lambda: _reject_keyword(opts.alternate.cast_for_cleave, paid.cleave, name, "cleave"),
        lambda: _reject_keyword(opts.costs.paid_conspire, paid.conspire, name, "conspire"),
        lambda: conspire_error(
            card_info,
            opts.costs.paid_conspire,
            ctx.zones,
            ctx.player_idx,
        ),
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
            ctx.zones,
            ctx.player_idx,
            card_info,
            opts.alternate.cast_for_emerge,
            list(opts.modifiers.targeting.emerge_sacrifice_ids),
        ),
        lambda: _reject_keyword(opts.alternate.cast_for_mutate, paid.mutate, name, "mutate"),
        lambda: mutate_host_error(
            ctx.zones,
            ctx.player_idx,
            card_info,
            opts.modifiers.targeting.mutate_target_uid,
        ),
        lambda: spree_selection_error(
            card_info,
            list(opts.modifiers.targeting.spree_mode_indices),
        ),
        lambda: _reject_keyword(opts.costs.paid_casualty, paid.casualty, name, "casualty"),
        lambda: casualty_sacrifice_error(
            ctx.zones,
            ctx.player_idx,
            card_info,
            opts.costs.paid_casualty,
            list(opts.modifiers.targeting.casualty_sacrifice_ids),
        ),
    ])
    if err:
        return None, err

    emerge_sacrifice_id = normalize_emerge_sacrifice_id(
        card_info,
        opts.alternate.cast_for_emerge,
        list(opts.modifiers.targeting.emerge_sacrifice_ids),
    )
    casualty_sacrifice_id = normalize_casualty_sacrifice_id(
        card_info,
        opts.costs.paid_casualty,
        list(opts.modifiers.targeting.casualty_sacrifice_ids),
    )
    cast_target_uid = (
        opts.modifiers.targeting.mutate_target_uid
        or opts.modifiers.targeting.bestow_target_uid
        or target_uid_str
    )
    return PaidAnnounceCast(
        modifiers=paid,
        emerge_sacrifice_id=emerge_sacrifice_id,
        casualty_sacrifice_id=casualty_sacrifice_id,
        cast_target_uid=cast_target_uid,
    ), None
