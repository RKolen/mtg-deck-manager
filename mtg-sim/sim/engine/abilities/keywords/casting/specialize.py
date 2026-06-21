"""Specialize: discard to cast a specialized version (simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting._hand_discard import (
    discard_hand_card_name,
    hand_discard_error,
)
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager

_SPECIALIZE_RE = re.compile(
    r'specialize\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_specialize(card: CardInfo) -> bool:
    """Return True when the card has specialize."""
    return has_registered_keyword(card.oracle_text, 'Specialize') or bool(
        _SPECIALIZE_RE.search(card.oracle_text or '')
    )


def specialize_cost(card: CardInfo) -> ManaCost | None:
    """Parse the specialize cost from oracle text."""
    match = _SPECIALIZE_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def specialize_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the specialize cost."""
    return alt_cost_mana_needed(specialize_cost(card), card)


def normalize_specialize_cast(card: CardInfo, cast_for_specialize: bool) -> bool:
    """Return whether this cast uses specialize."""
    return cast_for_specialize and has_specialize(card)


def specialize_discard_error(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int | None,
    *,
    paid: bool,
) -> str | None:
    """Return an error when specialize was announced without a discard."""
    if not paid:
        return None
    return hand_discard_error(
        zones,
        player_idx,
        hand_idx,
        missing_message='Specialize requires a card to discard',
    )


def discard_for_specialize(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int | None,
) -> str | None:
    """Discard the specialize cost card from hand."""
    return discard_hand_card_name(zones, player_idx, hand_idx)
