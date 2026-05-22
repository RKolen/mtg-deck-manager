"""Resolve mana for casts with optional overload, bestow, entwine, and kicker."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.casting.bestow import (
    bestow_mana_needed,
    normalize_bestow,
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
from engine.abilities.keywords.casting.replicate import replicate_extra_mana
def _payment_requirements(card: CardInfo) -> tuple[int, int]:
    """Return base mana and life for simplified payment (avoids game package import)."""
    phyrexian_pips = (card.mana_cost or '').upper().count('/P')
    total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
    return max(0, total_cmc - phyrexian_pips), phyrexian_pips * 2


def resolve_announce_cast_mana(
    card: CardInfo,
    *,
    kicker_times: int,
    entwined: bool,
    overloaded: bool,
    bestow_target_uid: str | None,
    cast_for_miracle: bool = False,
    replicate_times: int = 0,
) -> tuple[int, int]:
    """Return mana, life, and optional costs applied in priority order."""
    if normalize_miracle_cast(card, cast_for_miracle):
        mana_needed, life_cost = miracle_mana_needed(card)
    elif normalize_overloaded(card, overloaded):
        mana_needed, life_cost = overload_mana_needed(card)
    elif normalize_bestow(card, bestow_target_uid):
        mana_needed, life_cost = bestow_mana_needed(card)
    elif has_kicker(card):
        mana_needed, life_cost = cast_mana_needed(card, kicker_times)
    else:
        mana_needed, life_cost = _payment_requirements(card)
    mana_needed, life_cost = cast_mana_with_entwine(
        card,
        mana_needed,
        life_cost,
        entwined,
    )
    mana_needed += replicate_extra_mana(card, replicate_times)
    return mana_needed, life_cost
