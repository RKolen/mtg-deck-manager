"""Undaunted: costs {1} less for each opponent (CR 702.125)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_state import GameState


def has_undaunted(card: CardInfo) -> bool:
    """Return True when the card has undaunted."""
    return has_registered_keyword(card.oracle_text, 'Undaunted')


def opponent_count(game: GameState, controller_idx: int) -> int:
    """Count opponents still in the game."""
    return sum(
        1
        for idx, player in enumerate(game.players)
        if idx != controller_idx and not player.has_lost
    )


def undaunted_reduction(game: GameState, card: CardInfo, controller_idx: int) -> int:
    """Return generic mana discount from undaunted."""
    if not has_undaunted(card):
        return 0
    return opponent_count(game, controller_idx)
