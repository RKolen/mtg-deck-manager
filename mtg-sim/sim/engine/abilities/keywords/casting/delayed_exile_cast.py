"""Shared helpers for foretell, plot, and other exile-then-cast keywords."""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager


@dataclass(frozen=True)
class _CastTiming:
    """Encapsulates phase and stack state for timing checks."""

    phase: str
    stack_is_empty: bool


@dataclass(frozen=True)
class DelayedCastCheck:
    """Validation inputs for a delayed-cast setup or resolution."""

    card_allowed: bool
    timing_allowed: bool
    card_error: str
    timing_error: str


def main_phase_empty_stack(phase: str, stack_is_empty: bool) -> bool:
    """Return True during a main phase with an empty stack."""
    return phase in ('main1', 'main2') and stack_is_empty


def hand_setup_error(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
) -> str | None:
    """Return an error message when a hand index is invalid."""
    hand = zones.player_zones[player_idx].hand
    if hand_idx < 0 or hand_idx >= len(hand):
        return f"Hand index {hand_idx} out of range"
    card = hand[hand_idx]
    if not isinstance(card, CardObject):
        return "Invalid card"
    return None


def exile_from_hand_for_cast(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
    cast_mode: str,
) -> CardObject:
    """Exile a card from hand with a delayed-cast mode tag (after hand_setup_error)."""
    hand = zones.player_zones[player_idx].hand
    card = hand.pop(hand_idx)
    assert isinstance(card, CardObject)
    card.exiled_cast_mode = cast_mode
    zones.player_zones[player_idx].exile.append(card)
    return card


def exiled_cast_index_error(
    zones: ZoneManager,
    player_idx: int,
    exile_idx: int,
    expected_mode: str,
) -> tuple[str | None, CardObject | None]:
    """Return an error message and card when an exiled cast index is invalid."""
    exile = zones.player_zones[player_idx].exile
    if exile_idx < 0 or exile_idx >= len(exile):
        return f"Exile index {exile_idx} out of range", None
    card = exile[exile_idx]
    if not isinstance(card, CardObject):
        return "Invalid card", None
    if card.exiled_cast_mode != expected_mode:
        return f"That card was not exiled for {expected_mode}", None
    return None, card


def delayed_hand_setup_error(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
    check: DelayedCastCheck,
) -> str | None:
    """Return an error message for a delayed-cast setup from hand."""
    message: str | None = None
    if not check.card_allowed:
        message = check.card_error
    elif not check.timing_allowed:
        message = check.timing_error
    else:
        message = hand_setup_error(zones, player_idx, hand_idx)
    return message


def delayed_exile_cast_error(
    zones: ZoneManager,
    player_idx: int,
    exile_idx: int,
    expected_mode: str,
    check: DelayedCastCheck,
) -> str | None:
    """Return an error message for casting a delayed-cast card from exile."""
    message: str | None = None
    if not check.card_allowed:
        message = check.card_error
    elif not check.timing_allowed:
        message = check.timing_error
    else:
        message, _card = exiled_cast_index_error(
            zones,
            player_idx,
            exile_idx,
            expected_mode,
        )
    return message


def cast_from_delayed_exile(
    zones: ZoneManager,
    player_idx: int,
    exile_idx: int,
) -> CardObject:
    """Remove a delayed-cast card from exile to cast it (after delayed_exile_cast_error)."""
    exile = zones.player_zones[player_idx].exile
    card = exile.pop(exile_idx)
    assert isinstance(card, CardObject)
    card.exiled_cast_mode = None
    return card
