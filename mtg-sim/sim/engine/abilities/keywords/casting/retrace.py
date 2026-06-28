"""Retrace: cast from graveyard by discarding a land (CR 702.79)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords import has_flash
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.casting._hand_discard import (
    hand_discard_error,
    pop_hand_to_graveyard,
)
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager

_RETRACE_RE = re.compile(r'\bretrace\b', re.IGNORECASE)


def has_retrace(card: CardInfo) -> bool:
    """Return True when the card may be cast using retrace."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Retrace') or bool(_RETRACE_RE.search(text))


def has_retrace_card(card: CardInfo) -> bool:
    """Return True when the card has retrace."""
    return has_retrace(card)


def retrace_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for a retrace cast (normal spell cost)."""
    phyrexian_pips = (card.mana_cost or '').upper().count('/P')
    total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
    return max(0, total_cmc - phyrexian_pips)


def retrace_life_cost(card: CardInfo) -> int:
    """Return life to pay for phyrexian mana on a retrace cast."""
    return (card.mana_cost or '').upper().count('/P') * 2


def can_cast_via_retrace(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when retrace may be cast in the current timing window."""
    if card.is_land or not has_retrace(card):
        return False
    if has_flash(card):
        return phase in ('main1', 'main2', 'attack', 'declare_blockers')
    return phase in ('main1', 'main2') and stack_is_empty


def _hand_land(card: CardObject) -> bool:
    """Return True when the card object is a land."""
    return card.card_info is not None and card.card_info.is_land


def retrace_land_discard_error(
    zones: ZoneManager,
    player_idx: int,
    discard_hand_idx: int | None,
) -> str | None:
    """Return an error message when the retrace land discard is illegal."""

    def _land_only(card: CardObject) -> str | None:
        if not _hand_land(card):
            return "Retrace requires discarding a land card"
        return None

    return hand_discard_error(
        zones,
        player_idx,
        discard_hand_idx,
        missing_message="Retrace requires discarding a land card",
        validate_card=_land_only,
    )


def discard_land_for_retrace(
    zones: ZoneManager,
    player_idx: int,
    discard_hand_idx: int,
) -> CardObject:
    """Discard a land from hand to pay retrace (call after retrace_land_discard_error)."""
    return pop_hand_to_graveyard(zones, player_idx, discard_hand_idx)
