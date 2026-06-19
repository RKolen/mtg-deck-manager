"""Surge: alternate cost when an opponent was dealt damage this turn."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_state import GameState
from engine.core.mana import ManaCost

_SURGE_COST_RE = re.compile(
    r'surge\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_surge(card: CardInfo) -> bool:
    """Return True when the card has surge."""
    return has_registered_keyword(card.oracle_text, 'Surge') or bool(
        _SURGE_COST_RE.search(card.oracle_text or '')
    )


def surge_cost(card: CardInfo) -> ManaCost | None:
    """Parse the surge alternate cost from oracle text."""
    match = _SURGE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def surge_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the surge cost instead of the mana cost."""
    return alt_cost_mana_needed(surge_cost(card), card)


def surge_available(game: GameState, controller_idx: int) -> bool:
    """Return True when an opponent was dealt damage this turn."""
    opponent = 1 - controller_idx
    return game.players[opponent].was_dealt_damage_this_turn


def normalize_surge_cast(
    card: CardInfo,
    cast_for_surge: bool,
    *,
    available: bool,
) -> bool:
    """Return whether this cast uses the surge cost."""
    if not cast_for_surge or not has_surge(card):
        return False
    return available
