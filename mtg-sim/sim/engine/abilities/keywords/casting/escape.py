"""Escape: cast from graveyard for an alternate cost and exile other cards (CR 702.59)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.actions._parse import word_to_int
from engine.abilities.keywords.casting._indices import normalize_unique_indices
from engine.abilities.keywords.casting._timing import INSTANT_SPEED_PHASES
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager

_ESCAPE_COST_RE = re.compile(
    r'escape[—\-–]?\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_ESCAPE_EXILE_RE = re.compile(
    r'exile (\w+) other cards',
    re.IGNORECASE,
)
def has_escape(card: CardInfo) -> bool:
    """Return True when the card may be cast for its escape cost."""
    return has_registered_keyword(card.oracle_text, 'Escape') or bool(
        _ESCAPE_COST_RE.search(card.oracle_text or '')
    )


def escape_cost(card: CardInfo) -> ManaCost | None:
    """Parse the escape alternate mana cost from oracle text."""
    match = _ESCAPE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def escape_exiles_required(card: CardInfo) -> int:
    """Return how many other graveyard cards must be exiled to escape."""
    match = _ESCAPE_EXILE_RE.search(card.oracle_text or '')
    if match is None:
        return 4
    return word_to_int(match.group(1))


def escape_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for an escape cast (simplified payment)."""
    cost = escape_cost(card)
    if cost is None:
        return max(0, int(card.cmc) if card.cmc == int(card.cmc) else int(card.cmc))
    return cost.mana_value


def can_cast_via_escape(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when escape may be cast in the current timing window."""
    if card.is_land or not has_escape(card):
        return False
    if phase in INSTANT_SPEED_PHASES:
        return True
    return phase in ('main1', 'main2') and stack_is_empty


def normalize_escape_exile_indices(
    _card: CardInfo,
    graveyard_indices: list[int],
) -> list[int]:
    """Return deduped graveyard indices of cards to exile for escape."""
    return normalize_unique_indices(graveyard_indices)


def escape_payment_error(
    zones: ZoneManager,
    player_idx: int,
    spell_graveyard_idx: int,
    exile_indices: list[int],
    card: CardInfo,
) -> str | None:
    """Return an error message when escape costs cannot be paid."""
    required = escape_exiles_required(card)
    if len(exile_indices) < required:
        return (
            f"Escape requires exiling {required} other cards "
            f"({len(exile_indices)} selected)"
        )
    graveyard = zones.player_zones[player_idx].graveyard
    spell_card = (
        graveyard[spell_graveyard_idx]
        if 0 <= spell_graveyard_idx < len(graveyard)
        else None
    )
    if not isinstance(spell_card, CardObject):
        return "Escape spell is not a card"
    capped = exile_indices[:required]
    for idx in capped:
        if idx == spell_graveyard_idx:
            return "Cannot exile the card being cast for escape"
        if idx < 0 or idx >= len(graveyard):
            return f"Escape exile index {idx} out of range"
        other = graveyard[idx]
        if not isinstance(other, CardObject):
            return f"Escape exile index {idx} is not a card"
    return None


def exile_for_escape_cost(
    zones: ZoneManager,
    player_idx: int,
    exile_indices: list[int],
    card: CardInfo,
) -> list[int]:
    """Exile other graveyard cards for escape (call after escape_payment_error passes)."""
    required = escape_exiles_required(card)
    capped = normalize_escape_exile_indices(card, exile_indices)[:required]
    graveyard = zones.player_zones[player_idx].graveyard
    cards_to_exile = [graveyard[idx] for idx in capped]
    for other in cards_to_exile:
        assert isinstance(other, CardObject)
        zones.exile_from_graveyard(other, player_idx)
    return capped
