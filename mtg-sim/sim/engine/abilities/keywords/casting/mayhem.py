"""Mayhem: cast from graveyard after playing a land this turn (simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting._timing import INSTANT_SPEED_PHASES
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_state import GameState
from engine.core.mana import ManaCost

_MAYHEM_RE = re.compile(
    r'mayhem\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_mayhem(card: CardInfo) -> bool:
    """Return True when the card has mayhem."""
    return has_registered_keyword(card.oracle_text, 'Mayhem') or bool(
        _MAYHEM_RE.search(card.oracle_text or '')
    )


def mayhem_cost(card: CardInfo) -> ManaCost | None:
    """Parse the mayhem alternate cost from oracle text."""
    match = _MAYHEM_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def mayhem_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the mayhem cost."""
    return alt_cost_mana_needed(mayhem_cost(card), card)


def mayhem_available(game: GameState, controller_idx: int) -> bool:
    """Return True when the controller played a land this turn."""
    return game.players[controller_idx].land_played


def can_cast_via_mayhem(
    card: CardInfo,
    phase: str,
    stack_is_empty: bool,
    *,
    land_played: bool,
) -> bool:
    """Return True when mayhem may be cast from the graveyard."""
    if card.is_land or not has_mayhem(card) or not land_played:
        return False
    if phase in INSTANT_SPEED_PHASES:
        return True
    return phase in ('main1', 'main2') and stack_is_empty
