"""Dredge: replace a draw with milling cards from your library."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.actions._parse import word_to_int
from engine.abilities.keywords.actions.library import mill_cards
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager

_DREDGE_RE = re.compile(r'dredge\s+(\w+|\d+)', re.IGNORECASE)


def has_dredge(card: CardInfo) -> bool:
    """Return True when the card has dredge."""
    return has_registered_keyword(card.oracle_text, 'Dredge') or bool(
        _DREDGE_RE.search(card.oracle_text or '')
    )


def has_dredge_card(card: CardInfo) -> bool:
    """Return True when the card has dredge."""
    return has_dredge(card)


def dredge_amount(card: CardInfo) -> int:
    """Return how many cards to mill for this card's dredge ability."""
    match = _DREDGE_RE.search(card.oracle_text or '')
    if match is None:
        return 2
    return word_to_int(match.group(1))


def can_dredge_instead_of_draw(card: CardInfo, phase: str) -> bool:
    """Return True when dredge may replace a draw step draw."""
    return has_dredge(card) and phase == 'draw'


def apply_dredge(
    zones: ZoneManager,
    player_idx: int,
    graveyard_idx: int,
) -> tuple[str | None, str | None, list[CardObject]]:
    """Mill for dredge; the dredge card stays in the graveyard."""
    graveyard = zones.player_zones[player_idx].graveyard
    if graveyard_idx < 0 or graveyard_idx >= len(graveyard):
        return 'Graveyard index out of range', None, []
    card = graveyard[graveyard_idx]
    if not isinstance(card, CardObject) or card.card_info is None:
        return 'Invalid dredge card', None, []
    card_info = card.card_info
    if not has_dredge(card_info):
        return f'{card_info.name} does not have dredge', None, []
    milled = mill_cards(zones, player_idx, dredge_amount(card_info))
    names = ', '.join(c.card_info.name for c in milled if c.card_info)
    detail = f"dredge {card_info.name} milled {len(milled)}"
    if names:
        detail = f"{detail} ({names})"
    return None, detail, milled
