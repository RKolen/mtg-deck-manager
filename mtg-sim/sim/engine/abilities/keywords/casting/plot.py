"""Plot: exile a sorcery from hand, cast it later without paying mana (CR 702.167)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.delayed_exile_cast import (
    DelayedCastCheck,
    cast_from_delayed_exile,
    delayed_exile_cast_error,
    delayed_hand_setup_error,
    exile_from_hand_for_cast,
    main_phase_empty_stack,
)
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager

_PLOT_RE = re.compile(r'\bplot\b', re.IGNORECASE)
PLOT_EXILE_MODE = 'plot'


def has_plot(card: CardInfo) -> bool:
    """Return True when the card has plot."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Plot') or bool(_PLOT_RE.search(text))


def is_plottable_sorcery(card: CardInfo) -> bool:
    """Return True when the card is a sorcery that may be plotted."""
    return has_plot(card) and 'Sorcery' in card.type_line and not card.is_land


def can_plot_setup(phase: str, stack_is_empty: bool) -> bool:
    """Return True when plot setup may be started (simplified: main phase)."""
    return main_phase_empty_stack(phase, stack_is_empty)


def can_cast_plotted(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when a plotted sorcery may be cast."""
    return is_plottable_sorcery(card) and main_phase_empty_stack(phase, stack_is_empty)


def plot_setup_error(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
    card_info: CardInfo,
    phase: str,
    stack_is_empty: bool,
) -> str | None:
    """Return an error message when plotting from hand is illegal."""
    check = DelayedCastCheck(
        card_allowed=is_plottable_sorcery(card_info),
        timing_allowed=can_plot_setup(phase, stack_is_empty),
        card_error=f"{card_info.name} cannot be plotted",
        timing_error="Cannot plot now",
    )
    return delayed_hand_setup_error(zones, player_idx, hand_idx, check)


def exile_for_plot(zones: ZoneManager, player_idx: int, hand_idx: int) -> CardObject:
    """Exile a sorcery from hand to plot it (after plot_setup_error)."""
    return exile_from_hand_for_cast(zones, player_idx, hand_idx, PLOT_EXILE_MODE)


def plotted_cast_error(
    zones: ZoneManager,
    player_idx: int,
    exile_idx: int,
    card_info: CardInfo,
    phase: str,
    stack_is_empty: bool,
) -> str | None:
    """Return an error message when casting a plotted card is illegal."""
    check = DelayedCastCheck(
        card_allowed=is_plottable_sorcery(card_info),
        timing_allowed=can_cast_plotted(card_info, phase, stack_is_empty),
        card_error=f"{card_info.name} cannot be plotted",
        timing_error="Cannot cast plotted card now",
    )
    return delayed_exile_cast_error(zones, player_idx, exile_idx, PLOT_EXILE_MODE, check)


def cast_from_plot_exile(zones: ZoneManager, player_idx: int, exile_idx: int) -> CardObject:
    """Remove a plotted card from exile to cast it (after plotted_cast_error)."""
    return cast_from_delayed_exile(zones, player_idx, exile_idx)
