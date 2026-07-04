"""Resolve mana for casts with optional overload, bestow, entwine, and kicker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords.casting.bestow import (
    bestow_mana_needed,
    normalize_bestow,
)
from engine.abilities.keywords.casting.emerge import (
    emerge_mana_needed,
    normalize_emerge_cast,
)
from engine.abilities.keywords.casting.evoke import (
    evoke_mana_needed,
    normalize_evoke_cast,
)
from engine.abilities.keywords.casting.mutate import (
    mutate_mana_needed,
    normalize_mutate_cast,
)
from engine.abilities.keywords.casting.entwine import cast_mana_with_entwine
from engine.abilities.keywords.casting.kicker import cast_mana_needed, has_kicker
from engine.abilities.keywords.casting.freerunning import (
    freerunning_mana_needed,
    normalize_freerunning_cast,
)
from engine.abilities.keywords.casting.miracle import (
    miracle_mana_needed,
    normalize_miracle_cast,
)
from engine.abilities.keywords.casting.spectacle import (
    normalize_spectacle_cast,
    spectacle_mana_needed,
)
from engine.abilities.keywords.casting.surge import (
    normalize_surge_cast,
    surge_mana_needed,
)
from engine.abilities.keywords.casting.blitz import (
    blitz_mana_needed,
    normalize_blitz_cast,
)
from engine.abilities.keywords.casting.cleave import (
    cleave_mana_needed,
    normalize_cleave_cast,
)
from engine.abilities.keywords.casting.conspire import conspire_extra_mana
from engine.abilities.keywords.casting.escalate import escalate_extra_mana
from engine.abilities.keywords.casting.awaken import awaken_mana_extra
from engine.abilities.keywords.casting.impending import impending_mana_extra
from engine.abilities.keywords.casting.offering import offering_mana_reduction
from engine.abilities.keywords.casting.prototype import (
    normalize_prototype_cast,
    prototype_mana_needed,
)
from engine.abilities.keywords.casting.compleated import compleated_life_extra
from engine.abilities.keywords.casting.tiered import tiered_extra_mana
from engine.abilities.keywords.casting.undaunted import undaunted_reduction
from engine.abilities.keywords.casting.specialize import (
    normalize_specialize_cast,
    specialize_mana_needed,
)
from engine.abilities.keywords.casting.warp import normalize_warp_cast, warp_mana_needed
from engine.core.mana import ManaCost
from engine.game.cast_alt_mode_flags import AltCastModeFlags
from engine.abilities.keywords.casting.web_slinging import (
    normalize_web_slinging_cast,
    web_slinging_mana_needed,
)
from engine.abilities.keywords.casting.more_than_meets_the_eye import (
    more_than_meets_the_eye_mana_needed,
    normalize_more_than_meets_the_eye_cast,
)
from engine.abilities.keywords.casting.splice import splice_mana_extra
from engine.abilities.keywords.casting.dash import (
    dash_mana_needed,
    normalize_dash_cast,
)
from engine.abilities.keywords.other.disguise import (
    disguise_face_down_mana_needed,
    normalize_disguise_cast,
)
from engine.abilities.keywords.other.morph import (
    morph_face_down_mana_needed,
    normalize_morph_cast,
)
from engine.abilities.keywords.casting.overload import (
    normalize_overloaded,
    overload_mana_needed,
)
from engine.abilities.keywords.casting.buyback import buyback_extra_mana
from engine.abilities.keywords.casting.replicate import replicate_extra_mana
from engine.abilities.keywords.casting.squad import squad_extra_mana
from engine.abilities.keywords.casting.spree import spree_extra_mana
from engine.abilities.keywords.other.affinity import affinity_reduction
from engine.game.face_alternate_cast import FaceAlternateCastFlags

if TYPE_CHECKING:
    from engine.core.game_state import GameState
    from engine.core.zones import ZoneManager


@dataclass(frozen=True)
class _FlatBoolMods:
    """Simple boolean cost modifiers."""

    entwined: bool = False
    overloaded: bool = False
    paid_buyback: bool = False


@dataclass(frozen=True)
class _SacManaModifiers:
    """Sacrifice-based alternate cast modifiers."""

    cast_for_emerge: bool = False
    cast_for_evoke: bool = False
    cast_for_mutate: bool = False
    cast_for_offering: bool = False
    mutate_target_uid: str | None = None


@dataclass(frozen=True)
class _RepeatCastCounts:
    """Integer repeat costs such as replicate and squad."""

    replicate_times: int = 0
    squad_times: int = 0


@dataclass(frozen=True)
class _CastManaOptional:
    """Scalar optional costs for announce-cast mana."""

    kicker_times: int = 0
    bestow_target_uid: str | None = None
    spree_mode_indices: tuple[int, ...] = ()
    tiered_mode_index: int | None = None


@dataclass(frozen=True)
class CastManaModifiers:
    """Optional cost modifiers for announce-cast mana."""

    optional: _CastManaOptional = field(default_factory=_CastManaOptional)
    repeat: _RepeatCastCounts = field(default_factory=_RepeatCastCounts)
    bools: _FlatBoolMods = field(default_factory=_FlatBoolMods)
    sac: _SacManaModifiers = field(default_factory=_SacManaModifiers)
    face: FaceAlternateCastFlags = field(default_factory=FaceAlternateCastFlags)

    @property
    def kicker_times(self) -> int:
        """Number of times kicker was paid."""
        return self.optional.kicker_times

    @property
    def bestow_target_uid(self) -> str | None:
        """Bestow host UID when bestow was paid."""
        return self.optional.bestow_target_uid

    @property
    def spree_mode_indices(self) -> tuple[int, ...]:
        """Chosen spree mode indices."""
        return self.optional.spree_mode_indices

    @property
    def tiered_mode_index(self) -> int | None:
        """Chosen tiered mode index."""
        return self.optional.tiered_mode_index

    @property
    def replicate_times(self) -> int:
        """Number of times replicate was paid."""
        return self.repeat.replicate_times

    @property
    def squad_times(self) -> int:
        """Number of times squad was paid."""
        return self.repeat.squad_times

    @property
    def entwined(self) -> bool:
        """Whether entwine was paid."""
        return self.bools.entwined

    @property
    def overloaded(self) -> bool:
        """Whether overload was paid."""
        return self.bools.overloaded

    @property
    def paid_buyback(self) -> bool:
        """Whether buyback was paid."""
        return self.bools.paid_buyback

    @property
    def cast_for_emerge(self) -> bool:
        """Whether casting for emerge."""
        return self.sac.cast_for_emerge

    @property
    def cast_for_evoke(self) -> bool:
        """Whether casting for evoke."""
        return self.sac.cast_for_evoke

    @property
    def cast_for_mutate(self) -> bool:
        """Whether casting for mutate."""
        return self.sac.cast_for_mutate

    @property
    def cast_for_offering(self) -> bool:
        """Whether casting for offering."""
        return self.sac.cast_for_offering

    @property
    def mutate_target_uid(self) -> str | None:
        """Mutate target UID."""
        return self.sac.mutate_target_uid


@dataclass(frozen=True)
class _PaidTimingExtras:
    """Extra timing payments applied after alternate costs."""

    paid_awaken: bool = False
    paid_impending: bool = False
    paid_splice: bool = False
    paid_compleated: bool = False


@dataclass(frozen=True)
class _TimingAvailability:
    """Alternate cost availability for timing-sensitive casts."""

    freerunning_available: bool = False
    spectacle_available: bool = False
    surge_available: bool = False
    escalate_extra_targets: int = 0
    paid: _PaidTimingExtras = field(default_factory=_PaidTimingExtras)

    @property
    def paid_awaken(self) -> bool:
        """Whether awaken extra mana was paid."""
        return self.paid.paid_awaken

    @property
    def paid_impending(self) -> bool:
        """Whether impending extra mana was paid."""
        return self.paid.paid_impending

    @property
    def paid_splice(self) -> bool:
        """Whether splice extra mana was paid."""
        return self.paid.paid_splice

    @property
    def paid_compleated(self) -> bool:
        """Whether compleated extra life was paid."""
        return self.paid.paid_compleated


@dataclass(frozen=True)
class _OpponentDamageCasts:
    """Alternate costs gated on opponent damage or life loss."""

    spectacle: bool = False
    surge: bool = False


@dataclass(frozen=True)
class _FaceCastTiming:
    """Face-down and prototype alternate cast timing."""

    morph: bool = False
    prototype: bool = False


@dataclass(frozen=True)
class _DirectTimingCasts:
    """Timing-based alternate costs selected at announce."""

    miracle: bool = False
    freerunning: bool = False
    cleave: bool = False
    alt_modes: AltCastModeFlags = field(default_factory=AltCastModeFlags)


@dataclass(frozen=True)
class CastManaTiming:
    """Timing-sensitive alternate costs for announce-cast mana."""

    direct: _DirectTimingCasts = field(default_factory=_DirectTimingCasts)
    opponent_damage: _OpponentDamageCasts = field(default_factory=_OpponentDamageCasts)
    face: _FaceCastTiming = field(default_factory=_FaceCastTiming)
    paid_conspire: bool = False
    available: _TimingAvailability = field(default_factory=_TimingAvailability)

    @property
    def cast_for_miracle(self) -> bool:
        """Whether miracle was announced."""
        return self.direct.miracle

    @property
    def cast_for_freerunning(self) -> bool:
        """Whether freerunning was announced."""
        return self.direct.freerunning

    @property
    def cast_for_cleave(self) -> bool:
        """Whether cleave was announced."""
        return self.direct.cleave

    @property
    def cast_for_warp(self) -> bool:
        """Whether warp was announced."""
        return self.direct.alt_modes.warp

    @property
    def cast_for_web_slinging(self) -> bool:
        """Whether web-slinging was announced."""
        return self.direct.alt_modes.web_slinging

    @property
    def cast_for_converted(self) -> bool:
        """Whether More Than Meets the Eye was announced."""
        return self.direct.alt_modes.converted

    @property
    def cast_for_specialize(self) -> bool:
        """Whether specialize was announced."""
        return self.direct.alt_modes.specialize

    @property
    def cast_for_morph(self) -> bool:
        """Whether morph was announced."""
        return self.face.morph

    @property
    def cast_for_prototype(self) -> bool:
        """Whether prototype was announced."""
        return self.face.prototype

    @property
    def cast_for_spectacle(self) -> bool:
        """Whether spectacle was announced."""
        return self.opponent_damage.spectacle

    @property
    def cast_for_surge(self) -> bool:
        """Whether surge was announced."""
        return self.opponent_damage.surge

    @property
    def freerunning_available(self) -> bool:
        """Whether freerunning is available."""
        return self.available.freerunning_available

    @property
    def spectacle_available(self) -> bool:
        """Whether spectacle is available."""
        return self.available.spectacle_available

    @property
    def surge_available(self) -> bool:
        """Whether surge is available."""
        return self.available.surge_available


@dataclass(frozen=True)
class AnnounceCastManaOptions:
    """Optional costs included in announce-cast mana resolution."""

    modifiers: CastManaModifiers = field(default_factory=CastManaModifiers)
    timing: CastManaTiming = field(default_factory=CastManaTiming)
    zones: ZoneManager | None = None
    game: GameState | None = None
    controller_idx: int = 0


def _payment_requirements(card: CardInfo) -> tuple[int, int]:
    """Return base mana and life for simplified payment (avoids game package import)."""
    phyrexian_pips = (card.mana_cost or '').upper().count('/P')
    if card.mana_cost:
        mana_needed = max(0, ManaCost.parse(card.mana_cost).mana_value - phyrexian_pips)
    else:
        total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
        mana_needed = max(0, total_cmc - phyrexian_pips)
    return mana_needed, phyrexian_pips * 2


_TimingManaResolver = Callable[[CardInfo, CastManaTiming], tuple[int, int] | None]


def _miracle_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_miracle_cast(card, timing.cast_for_miracle):
        return miracle_mana_needed(card)
    return None


def _spectacle_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_spectacle_cast(
        card, timing.cast_for_spectacle, available=timing.spectacle_available
    ):
        return spectacle_mana_needed(card)
    return None


def _surge_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_surge_cast(card, timing.cast_for_surge, available=timing.surge_available):
        return surge_mana_needed(card)
    return None


def _prototype_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_prototype_cast(card, timing.cast_for_prototype):
        return prototype_mana_needed(card)
    return None


def _cleave_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_cleave_cast(card, timing.cast_for_cleave):
        return cleave_mana_needed(card)
    return None


def _freerunning_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_freerunning_cast(
        card, timing.cast_for_freerunning, timing.freerunning_available
    ):
        return freerunning_mana_needed(card)
    return None


def _warp_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_warp_cast(card, timing.cast_for_warp):
        return warp_mana_needed(card)
    return None


def _web_slinging_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_web_slinging_cast(card, timing.cast_for_web_slinging):
        return web_slinging_mana_needed(card)
    return None


def _converted_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_more_than_meets_the_eye_cast(card, timing.cast_for_converted):
        return more_than_meets_the_eye_mana_needed(card)
    return None


def _specialize_timing_mana(card: CardInfo, timing: CastManaTiming) -> tuple[int, int] | None:
    if normalize_specialize_cast(card, timing.cast_for_specialize):
        return specialize_mana_needed(card)
    return None


_TIMING_MANA_RESOLVERS: tuple[_TimingManaResolver, ...] = (
    _miracle_timing_mana,
    _spectacle_timing_mana,
    _surge_timing_mana,
    _prototype_timing_mana,
    _cleave_timing_mana,
    _freerunning_timing_mana,
    _warp_timing_mana,
    _web_slinging_timing_mana,
    _converted_timing_mana,
    _specialize_timing_mana,
)


def _resolve_timing_alternate_mana(
    card: CardInfo,
    timing: CastManaTiming,
) -> tuple[int, int] | None:
    """Return mana/life for timing-based alternate costs, or None if none apply."""
    for resolver in _TIMING_MANA_RESOLVERS:
        result = resolver(card, timing)
        if result is not None:
            return result
    return None


def _resolve_face_alternate_mana(
    card: CardInfo,
    mods: CastManaModifiers,
) -> tuple[int, int] | None:
    """Return mana/life for face-down alternate costs, or None if none apply."""
    if normalize_morph_cast(card, mods.face.cast_for_morph):
        return morph_face_down_mana_needed()
    if normalize_disguise_cast(card, mods.face.cast_for_disguise):
        return disguise_face_down_mana_needed()
    if normalize_dash_cast(card, mods.face.cast_for_dash):
        return dash_mana_needed(card)
    if normalize_blitz_cast(card, mods.face.cast_for_blitz):
        return blitz_mana_needed(card)
    return None


def _resolve_sac_alternate_mana(
    card: CardInfo,
    mods: CastManaModifiers,
) -> tuple[int, int] | None:
    """Return mana/life for sacrifice-based alternate costs, or None if none apply."""
    if normalize_overloaded(card, mods.overloaded):
        return overload_mana_needed(card)
    if normalize_evoke_cast(card, mods.cast_for_evoke):
        return evoke_mana_needed(card)
    if normalize_emerge_cast(card, mods.cast_for_emerge):
        return emerge_mana_needed(card)
    if normalize_mutate_cast(card, mods.cast_for_mutate, mods.mutate_target_uid):
        return mutate_mana_needed(card)
    if normalize_bestow(card, mods.bestow_target_uid):
        return bestow_mana_needed(card)
    return None


def resolve_announce_cast_mana(
    card: CardInfo,
    options: AnnounceCastManaOptions | None = None,
) -> tuple[int, int]:
    """Return mana, life, and optional costs applied in priority order."""
    opts = options or AnnounceCastManaOptions()
    mods = opts.modifiers
    timing = opts.timing
    base = (
        _resolve_timing_alternate_mana(card, timing)
        or _resolve_face_alternate_mana(card, mods)
        or _resolve_sac_alternate_mana(card, mods)
    )
    if base is not None:
        mana_needed, life_cost = base
    elif has_kicker(card):
        mana_needed, life_cost = cast_mana_needed(card, mods.kicker_times)
    else:
        mana_needed, life_cost = _payment_requirements(card)
    mana_needed, life_cost = cast_mana_with_entwine(card, mana_needed, life_cost, mods.entwined)
    mana_needed += replicate_extra_mana(card, mods.replicate_times)
    mana_needed += squad_extra_mana(card, mods.squad_times)
    mana_needed += buyback_extra_mana(card, mods.paid_buyback)
    mana_needed += spree_extra_mana(card, mods.spree_mode_indices)
    mana_needed += tiered_extra_mana(card, mods.tiered_mode_index)
    mana_needed += conspire_extra_mana(card, timing.paid_conspire)
    mana_needed += escalate_extra_mana(card, timing.available.escalate_extra_targets)
    mana_needed += awaken_mana_extra(card, timing.available.paid_awaken)
    mana_needed += impending_mana_extra(card, timing.available.paid_impending)
    mana_needed += splice_mana_extra(card, timing.available.paid_splice)
    mana_needed = max(
        0,
        mana_needed - offering_mana_reduction(card, mods.cast_for_offering),
    )
    if opts.zones is not None:
        mana_needed = max(
            0,
            mana_needed - affinity_reduction(card, opts.zones, opts.controller_idx),
        )
    if opts.game is not None:
        mana_needed = max(
            0,
            mana_needed - undaunted_reduction(opts.game, card, opts.controller_idx),
        )
    life_cost += compleated_life_extra(card, timing.available.paid_compleated)
    return mana_needed, life_cost
