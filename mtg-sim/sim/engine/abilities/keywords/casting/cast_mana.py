"""Resolve mana for casts with optional overload, bestow, entwine, and kicker."""

from __future__ import annotations

from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords.casting.bestow import (
    bestow_mana_needed,
    normalize_bestow,
)
from engine.abilities.keywords.casting.emerge import (
    emerge_mana_needed,
    normalize_emerge_cast,
)
from engine.abilities.keywords.casting.entwine import cast_mana_with_entwine
from engine.abilities.keywords.casting.kicker import cast_mana_needed, has_kicker
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


@dataclass(frozen=True)
class AnnounceCastManaOptions:
    """Optional costs included in announce-cast mana resolution."""

    kicker_times: int = 0
    entwined: bool = False
    overloaded: bool = False
    bestow_target_uid: str | None = None
    cast_for_miracle: bool = False
    replicate_times: int = 0
    paid_buyback: bool = False
    cast_for_emerge: bool = False


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
    if normalize_miracle_cast(card, opts.cast_for_miracle):
        mana_needed, life_cost = miracle_mana_needed(card)
    elif normalize_overloaded(card, opts.overloaded):
        mana_needed, life_cost = overload_mana_needed(card)
    elif normalize_emerge_cast(card, opts.cast_for_emerge):
        mana_needed, life_cost = emerge_mana_needed(card)
    elif normalize_bestow(card, opts.bestow_target_uid):
        mana_needed, life_cost = bestow_mana_needed(card)
    elif has_kicker(card):
        mana_needed, life_cost = cast_mana_needed(card, opts.kicker_times)
    else:
        mana_needed, life_cost = _payment_requirements(card)
    mana_needed, life_cost = cast_mana_with_entwine(
        card,
        mana_needed,
        life_cost,
        opts.entwined,
    )
    mana_needed += replicate_extra_mana(card, opts.replicate_times)
    mana_needed += buyback_extra_mana(card, opts.paid_buyback)
    return mana_needed, life_cost
