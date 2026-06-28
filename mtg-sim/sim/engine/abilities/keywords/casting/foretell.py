"""Foretell: exile from hand, then cast later for the foretell cost (CR 702.171)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.casting.delayed_exile_cast import (
    _CastTiming,
    DelayedCastCheck,
    cast_from_delayed_exile,
    delayed_exile_cast_error,
    delayed_hand_setup_error,
    exile_from_hand_for_cast,
    main_phase_empty_stack,
)
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager

_FORETELL_COST_RE = re.compile(
    r'foretell\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
FORETELL_SETUP_MANA = 0  # simplified; rules use {2} generic during your turn
FORETELL_EXILE_MODE = 'foretell'


def has_foretell(card: CardInfo) -> bool:
    """Return True when the card has foretell."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Foretell') or bool(_FORETELL_COST_RE.search(text))


def has_foretell_card(card: CardInfo) -> bool:
    """Return True when the card has foretell."""
    return has_foretell(card)


def foretell_cost(card: CardInfo) -> ManaCost | None:
    """Parse the foretell cast cost from oracle text."""
    match = _FORETELL_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def foretell_cast_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to cast a foretold card."""
    return alt_cost_mana_needed(foretell_cost(card), card)


def can_foretell_setup(phase: str, stack_is_empty: bool) -> bool:
    """Return True when a foretell setup may be started (simplified: main phase)."""
    return main_phase_empty_stack(phase, stack_is_empty)


def can_cast_foretold(card: CardInfo, timing: _CastTiming) -> bool:
    """Return True when a foretold card may be cast."""
    if card.is_land or not has_foretell(card):
        return False
    if 'Instant' in card.type_line:
        if timing.phase in ('main1', 'main2', 'attack', 'declare_blockers'):
            return True
        return timing.phase in ('main1', 'main2') and timing.stack_is_empty
    return timing.phase in ('main1', 'main2') and timing.stack_is_empty


def foretell_setup_error(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
    card_info: CardInfo,
    timing: _CastTiming,
) -> str | None:
    """Return an error message when foretell setup from hand is illegal."""
    check = DelayedCastCheck(
        card_allowed=has_foretell(card_info),
        timing_allowed=main_phase_empty_stack(timing.phase, timing.stack_is_empty),
        card_error=f"{card_info.name} does not have foretell",
        timing_error="Cannot foretell now",
    )
    return delayed_hand_setup_error(zones, player_idx, hand_idx, check)


def exile_for_foretell(zones: ZoneManager, player_idx: int, hand_idx: int) -> CardObject:
    """Exile a card from hand for foretell (after foretell_setup_error)."""
    return exile_from_hand_for_cast(zones, player_idx, hand_idx, FORETELL_EXILE_MODE)


def foretold_cast_error(
    zones: ZoneManager,
    player_idx: int,
    exile_idx: int,
    card_info: CardInfo,
    timing: _CastTiming,
) -> str | None:
    """Return an error message when casting a foretold card is illegal."""
    check = DelayedCastCheck(
        card_allowed=has_foretell(card_info),
        timing_allowed=can_cast_foretold(card_info, timing),
        card_error=f"{card_info.name} does not have foretell",
        timing_error="Cannot cast foretold card now",
    )
    return delayed_exile_cast_error(zones, player_idx, exile_idx, FORETELL_EXILE_MODE, check)


def cast_from_foretell_exile(zones: ZoneManager, player_idx: int, exile_idx: int) -> CardObject:
    """Remove a foretold card from exile to cast it (after foretold_cast_error)."""
    return cast_from_delayed_exile(zones, player_idx, exile_idx)
