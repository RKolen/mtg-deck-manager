"""Suspend: exile with time counters, then cast without paying (CR 702.61, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.casting.delayed_exile_cast import (
    DelayedCastCheck,
    hand_setup_error,
    main_phase_empty_stack,
)
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager

_SUSPEND_RE = re.compile(
    r'suspend\s*(\d+)\s*[—–-]\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
SUSPEND_EXILE_MODE = 'suspend'


def has_suspend(card: CardInfo) -> bool:
    """Return True when the card has suspend."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Suspend') or bool(
        _SUSPEND_RE.search(text)
    )


def has_suspend_card(card: CardInfo) -> bool:
    """Return True when the card has suspend."""
    return has_suspend(card)


def suspend_time_counters(card: CardInfo) -> int:
    """Return the number of time counters placed when suspending."""
    match = _SUSPEND_RE.search(card.oracle_text or '')
    if match is None:
        return 0
    return int(match.group(1))


def suspend_cost(card: CardInfo) -> ManaCost | None:
    """Parse the suspend cost from oracle text."""
    match = _SUSPEND_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(2))


def suspend_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the suspend cost."""
    return alt_cost_mana_needed(suspend_cost(card), card)


def can_suspend(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when a card may be suspended from hand."""
    if card.is_land or not has_suspend(card):
        return False
    return main_phase_empty_stack(phase, stack_is_empty)


def suspend_setup_error(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
    *,
    phase: str,
    stack_is_empty: bool,
) -> str | None:
    """Return an error message when suspend from hand is illegal."""
    hand_err = hand_setup_error(zones, player_idx, hand_idx)
    if hand_err is not None:
        return hand_err
    card = zones.player_zones[player_idx].hand[hand_idx]
    if not isinstance(card, CardObject):
        return "Invalid card"
    assert card.card_info is not None
    card_info = card.card_info
    check = DelayedCastCheck(
        card_allowed=has_suspend(card_info),
        timing_allowed=can_suspend(card_info, phase, stack_is_empty),
        card_error=f"{card_info.name} does not have suspend",
        timing_error="Cannot suspend now",
    )
    if not check.card_allowed:
        return check.card_error
    if not check.timing_allowed:
        return check.timing_error
    return None


def exile_for_suspend(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
    counters: int,
) -> CardObject:
    """Exile a card from hand with suspend counters (after suspend_setup_error)."""
    err = hand_setup_error(zones, player_idx, hand_idx)
    if err is not None:
        raise ValueError(err)
    hand = zones.player_zones[player_idx].hand
    card = hand.pop(hand_idx)
    assert isinstance(card, CardObject)
    card.exiled_cast_mode = SUSPEND_EXILE_MODE
    card.suspend_time_counters = counters
    zones.player_zones[player_idx].exile.append(card)
    return card


def tick_suspend_counters(
    zones: ZoneManager,
    player_idx: int,
) -> list[CardObject]:
    """Remove one time counter from each suspended card; return cards ready to cast."""
    ready: list[CardObject] = []
    for card in zones.player_zones[player_idx].exile:
        if not isinstance(card, CardObject):
            continue
        if card.exiled_cast_mode != SUSPEND_EXILE_MODE or card.suspend_time_counters <= 0:
            continue
        card.suspend_time_counters -= 1
        if card.suspend_time_counters == 0:
            card.exiled_cast_mode = None
            ready.append(card)
    return ready


def remove_suspended_card_from_exile(
    zones: ZoneManager,
    player_idx: int,
    card: CardObject,
) -> None:
    """Remove a suspended card from exile when it is cast."""
    exile = zones.player_zones[player_idx].exile
    if card in exile:
        exile.remove(card)
