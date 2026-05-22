"""Shared regex helpers for activated costs on cards (cycling, unearth, channel)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager

INSTANT_SPEED_PHASES = frozenset({
    "main1",
    "main2",
    "attack",
    "declare_blockers",
})


def timing_allows_hand_activation(phase: str, stack_is_empty: bool) -> bool:
    """Return True at instant speed or during a main phase with an empty stack."""
    if phase in INSTANT_SPEED_PHASES:
        return True
    return phase in ("main1", "main2") and stack_is_empty


def has_cost_keyword(card: CardInfo, keyword: str, pattern: re.Pattern[str]) -> bool:
    """Return True when oracle text has a registry keyword or regex cost match."""
    text = card.oracle_text or ""
    return has_registered_keyword(text, keyword) or bool(pattern.search(text))


def parse_alt_cost(card: CardInfo, pattern: re.Pattern[str]) -> ManaCost | None:
    """Parse an alternate cost from oracle text using pattern group 1."""
    match = pattern.search(card.oracle_text or "")
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def alt_cost_mana_value(card: CardInfo, pattern: re.Pattern[str]) -> int:
    """Return simplified land mana to pay for an alternate cost."""
    cost = parse_alt_cost(card, pattern)
    if cost is None:
        return 0
    return cost.mana_value


def discard_from_hand(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
) -> CardObject:
    """Move a card from hand to graveyard (cycling, channel, etc.)."""
    hand = zones.player_zones[player_idx].hand
    card = hand.pop(hand_idx)
    assert isinstance(card, CardObject)
    zones.player_zones[player_idx].graveyard.append(card)
    return card
