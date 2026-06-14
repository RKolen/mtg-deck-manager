"""Resolve mana for casts with optional overload, bestow, entwine, and kicker."""

from __future__ import annotations

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
from engine.abilities.keywords.casting.spree import spree_extra_mana
from engine.abilities.keywords.other.affinity import affinity_reduction
from engine.game.face_alternate_cast import FaceAlternateCastFlags

if TYPE_CHECKING:
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
    mutate_target_uid: str | None = None


@dataclass(frozen=True)
class CastManaModifiers:
    """Optional cost modifiers for announce-cast mana."""

    kicker_times: int = 0
    bestow_target_uid: str | None = None
    replicate_times: int = 0
    spree_mode_indices: tuple[int, ...] = ()
    bools: _FlatBoolMods = field(default_factory=_FlatBoolMods)
    sac: _SacManaModifiers = field(default_factory=_SacManaModifiers)
    face: FaceAlternateCastFlags = field(default_factory=FaceAlternateCastFlags)

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
    def mutate_target_uid(self) -> str | None:
        """Mutate target UID."""
        return self.sac.mutate_target_uid


@dataclass(frozen=True)
class _TimingAvailability:
    """Alternate cost availability for timing-sensitive casts."""

    freerunning_available: bool = False
    spectacle_available: bool = False
    escalate_extra_targets: int = 0
    paid_awaken: bool = False


@dataclass(frozen=True)
class CastManaTiming:
    """Timing-sensitive alternate costs for announce-cast mana."""

    cast_for_miracle: bool = False
    cast_for_freerunning: bool = False
    cast_for_spectacle: bool = False
    cast_for_cleave: bool = False
    cast_for_morph: bool = False
    paid_conspire: bool = False
    available: _TimingAvailability = field(default_factory=_TimingAvailability)

    @property
    def freerunning_available(self) -> bool:
        """Whether freerunning is available."""
        return self.available.freerunning_available

    @property
    def spectacle_available(self) -> bool:
        """Whether spectacle is available."""
        return self.available.spectacle_available


@dataclass(frozen=True)
class AnnounceCastManaOptions:
    """Optional costs included in announce-cast mana resolution."""

    modifiers: CastManaModifiers = field(default_factory=CastManaModifiers)
    timing: CastManaTiming = field(default_factory=CastManaTiming)
    zones: ZoneManager | None = None
    controller_idx: int = 0


def _payment_requirements(card: CardInfo) -> tuple[int, int]:
    """Return base mana and life for simplified payment (avoids game package import)."""
    phyrexian_pips = (card.mana_cost or '').upper().count('/P')
    total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
    return max(0, total_cmc - phyrexian_pips), phyrexian_pips * 2


def _resolve_timing_alternate_mana(
    card: CardInfo,
    timing: CastManaTiming,
) -> tuple[int, int] | None:
    """Return mana/life for timing-based alternate costs, or None if none apply."""
    if normalize_miracle_cast(card, timing.cast_for_miracle):
        return miracle_mana_needed(card)
    if normalize_spectacle_cast(
        card, timing.cast_for_spectacle, available=timing.spectacle_available
    ):
        return spectacle_mana_needed(card)
    if normalize_cleave_cast(card, timing.cast_for_cleave):
        return cleave_mana_needed(card)
    if normalize_freerunning_cast(card, timing.cast_for_freerunning, timing.freerunning_available):
        return freerunning_mana_needed(card)
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
    mana_needed += buyback_extra_mana(card, mods.paid_buyback)
    mana_needed += spree_extra_mana(card, mods.spree_mode_indices)
    mana_needed += conspire_extra_mana(card, timing.paid_conspire)
    mana_needed += escalate_extra_mana(card, timing.available.escalate_extra_targets)
    mana_needed += awaken_mana_extra(card, timing.available.paid_awaken)
    if opts.zones is not None:
        mana_needed = max(
            0,
            mana_needed - affinity_reduction(card, opts.zones, opts.controller_idx),
        )
    return mana_needed, life_cost
