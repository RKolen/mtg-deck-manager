"""Resolve mana for casts with optional overload, bestow, entwine, and kicker."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.casting.bestow import (
    bestow_mana_needed,
    normalize_bestow,
)
from engine.abilities.keywords.casting.entwine import cast_mana_with_entwine
from engine.abilities.keywords.casting.kicker import cast_mana_needed, has_kicker
from engine.abilities.keywords.casting.overload import (
    normalize_overloaded,
    overload_mana_needed,
)
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
) -> tuple[int, int]:
    """Return mana, life, and optional costs applied in priority order."""
    if normalize_overloaded(card, overloaded):
        return overload_mana_needed(card)
    if normalize_bestow(card, bestow_target_uid):
        return bestow_mana_needed(card)
    if has_kicker(card):
        mana_needed, life_cost = cast_mana_needed(card, kicker_times)
    else:
        mana_needed, life_cost = _payment_requirements(card)
    return cast_mana_with_entwine(card, mana_needed, life_cost, entwined)
