"""Dethrone: reward when dealing combat damage to the player with the most life."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_dethrone(perm: Permanent) -> bool:
    """Return True when the permanent has dethrone."""
    return has_keyword(perm, 'Dethrone')


def has_dethrone_card(card: CardInfo) -> bool:
    """Return True when the card has dethrone."""
    return has_registered_keyword(card.oracle_text, 'Dethrone')


def apply_dethrone_on_combat_damage_to_player(
    game: GameState,
    attacker: Permanent,
    damage: int,
    damaged_player_idx: int | None,
) -> str | None:
    """Apply dethrone when damage hits a player with the most life (1v1 simplified)."""
    if damage <= 0 or damaged_player_idx is None or not has_dethrone(attacker):
        return None
    attacker_life = game.players[attacker.controller_idx].life
    defender_life = game.players[damaged_player_idx].life
    if defender_life < attacker_life:
        return None
    if 'draw a card' in attacker.oracle_text.lower():
        return f"dethrone {attacker.name} (draw)"
    return f"dethrone {attacker.name}"
