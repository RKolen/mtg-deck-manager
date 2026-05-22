"""Jump-start: cast from graveyard by discarding and paying alt cost (CR 702.133)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.flashback import INSTANT_SPEED_PHASES
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.casting._hand_discard import (
    hand_discard_error,
    pop_hand_to_graveyard,
)
from engine.core.game_object import CardObject
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager

_JUMP_START_COST_RE = re.compile(
    r'jump-?start\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_jump_start(card: CardInfo) -> bool:
    """Return True when the card may be cast for its jump-start cost."""
    return has_registered_keyword(card.oracle_text, 'Jump-start') or bool(
        _JUMP_START_COST_RE.search(card.oracle_text or '')
    )


def jump_start_cost(card: CardInfo) -> ManaCost | None:
    """Parse the jump-start alternate cost from oracle text."""
    match = _JUMP_START_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def jump_start_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for a jump-start cast (simplified payment)."""
    cost = jump_start_cost(card)
    if cost is None:
        return max(0, int(card.cmc) if card.cmc == int(card.cmc) else int(card.cmc))
    return cost.mana_value


def can_cast_via_jump_start(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when jump-start may be cast in the current timing window."""
    if card.is_land or not has_jump_start(card):
        return False
    if phase in INSTANT_SPEED_PHASES:
        return True
    return phase in ('main1', 'main2') and stack_is_empty


def jump_start_discard_error(
    zones: ZoneManager,
    player_idx: int,
    discard_hand_idx: int | None,
) -> str | None:
    """Return an error message when the jump-start discard is illegal."""
    return hand_discard_error(
        zones,
        player_idx,
        discard_hand_idx,
        missing_message="Jump-start requires discarding a card",
    )


def discard_for_jump_start(
    zones: ZoneManager,
    player_idx: int,
    discard_hand_idx: int,
) -> CardObject:
    """Discard a card from hand to pay jump-start (call after jump_start_discard_error)."""
    return pop_hand_to_graveyard(zones, player_idx, discard_hand_idx)
