"""Aftermath: cast the graveyard half from your graveyard in a main phase (CR 702.127)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword


def has_aftermath(card: CardInfo) -> bool:
    """Return True when the card has an aftermath cast from the graveyard."""
    return has_registered_keyword(card.oracle_text, 'Aftermath')


def has_aftermath_card(card: CardInfo) -> bool:
    """Return True when the card has aftermath."""
    return has_aftermath(card)


def aftermath_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life needed to cast the aftermath half (simplified payment)."""
    phyrexian_pips = (card.mana_cost or '').upper().count('/P')
    total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
    return max(0, total_cmc - phyrexian_pips), phyrexian_pips * 2


def can_cast_aftermath(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when aftermath may be cast from the graveyard now.

    Aftermath may only be cast during your main phase while the stack is empty.
    """
    if card.is_land or not has_aftermath(card):
        return False
    return phase in ('main1', 'main2') and stack_is_empty
