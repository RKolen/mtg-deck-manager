"""Shared mana payment helpers for alternate casting costs."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.core.mana import ManaCost


def alt_cost_mana_needed(cost: ManaCost | None, card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay an alternate cost instead of the mana cost."""
    if cost is None:
        total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
        return max(0, total_cmc), 0
    phyrexian_pips = (card.mana_cost or '').upper().count('/P')
    return max(0, cost.mana_value - phyrexian_pips), phyrexian_pips * 2
