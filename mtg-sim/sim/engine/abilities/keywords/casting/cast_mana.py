"""Resolve mana for casts with optional overload, bestow, entwine, and kicker."""

from __future__ import annotations

from dataclasses import dataclass, field

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
from engine.abilities.keywords.casting.overload import (
    normalize_overloaded,
    overload_mana_needed,
)
from engine.abilities.keywords.casting.buyback import buyback_extra_mana
from engine.abilities.keywords.casting.replicate import replicate_extra_mana
from engine.abilities.keywords.casting.spree import spree_extra_mana


@dataclass(frozen=True)
class CastManaModifiers:
    """Optional cost modifiers for announce-cast mana."""

    kicker_times: int = 0
    entwined: bool = False
    overloaded: bool = False
    bestow_target_uid: str | None = None
    replicate_times: int = 0
    paid_buyback: bool = False
    cast_for_emerge: bool = False
    cast_for_evoke: bool = False
    cast_for_mutate: bool = False
    mutate_target_uid: str | None = None
    spree_mode_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class CastManaTiming:
    """Timing-sensitive alternate costs for announce-cast mana."""

    cast_for_miracle: bool = False
    cast_for_freerunning: bool = False
    freerunning_available: bool = False


@dataclass(frozen=True)
class AnnounceCastManaOptions:
    """Optional costs included in announce-cast mana resolution."""

    modifiers: CastManaModifiers = field(default_factory=CastManaModifiers)
    timing: CastManaTiming = field(default_factory=CastManaTiming)


def _payment_requirements(card: CardInfo) -> tuple[int, int]:
    """Return base mana and life for simplified payment (avoids game package import)."""
    phyrexian_pips = (card.mana_cost or '').upper().count('/P')
    total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
    return max(0, total_cmc - phyrexian_pips), phyrexian_pips * 2


def resolve_announce_cast_mana(
    card: CardInfo,
    options: AnnounceCastManaOptions | None = None,
) -> tuple[int, int]:
    """Return mana, life, and optional costs applied in priority order."""
    opts = options or AnnounceCastManaOptions()
    mods = opts.modifiers
    timing = opts.timing
    if normalize_miracle_cast(card, timing.cast_for_miracle):
        mana_needed, life_cost = miracle_mana_needed(card)
    elif normalize_freerunning_cast(
        card,
        timing.cast_for_freerunning,
        timing.freerunning_available,
    ):
        mana_needed, life_cost = freerunning_mana_needed(card)
    elif normalize_overloaded(card, mods.overloaded):
        mana_needed, life_cost = overload_mana_needed(card)
    elif normalize_evoke_cast(card, mods.cast_for_evoke):
        mana_needed, life_cost = evoke_mana_needed(card)
    elif normalize_emerge_cast(card, mods.cast_for_emerge):
        mana_needed, life_cost = emerge_mana_needed(card)
    elif normalize_mutate_cast(card, mods.cast_for_mutate, mods.mutate_target_uid):
        mana_needed, life_cost = mutate_mana_needed(card)
    elif normalize_bestow(card, mods.bestow_target_uid):
        mana_needed, life_cost = bestow_mana_needed(card)
    elif has_kicker(card):
        mana_needed, life_cost = cast_mana_needed(card, mods.kicker_times)
    else:
        mana_needed, life_cost = _payment_requirements(card)
    mana_needed, life_cost = cast_mana_with_entwine(
        card,
        mana_needed,
        life_cost,
        mods.entwined,
    )
    mana_needed += replicate_extra_mana(card, mods.replicate_times)
    mana_needed += buyback_extra_mana(card, mods.paid_buyback)
    mana_needed += spree_extra_mana(card, mods.spree_mode_indices)
    return mana_needed, life_cost
