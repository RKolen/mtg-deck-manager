"""Spectacle: alternate cost when an opponent lost life this turn (CR 702.136, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost
from engine.core.game_state import GameState

_SPECTACLE_COST_RE = re.compile(
    r'spectacle\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_spectacle(card: CardInfo) -> bool:
    """Return True when the card has spectacle."""
    return has_registered_keyword(card.oracle_text, 'Spectacle') or bool(
        _SPECTACLE_COST_RE.search(card.oracle_text or '')
    )


def spectacle_cost(card: CardInfo) -> ManaCost | None:
    """Parse the spectacle alternate cost from oracle text."""
    match = _SPECTACLE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def spectacle_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the spectacle cost instead of the mana cost."""
    return alt_cost_mana_needed(spectacle_cost(card), card)


def spectacle_available(game: GameState, controller_idx: int) -> bool:
    """Return True when an opponent lost life this turn (damage proxy)."""
    opponent = 1 - controller_idx
    return game.players[opponent].was_dealt_damage_this_turn


def normalize_spectacle_cast(
    card: CardInfo,
    cast_for_spectacle: bool,
    *,
    available: bool,
) -> bool:
    """Return whether this cast uses the spectacle cost."""
    if not cast_for_spectacle or not has_spectacle(card):
        return False
    return available
