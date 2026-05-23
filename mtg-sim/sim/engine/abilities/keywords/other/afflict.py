"""Afflict: attacking player loses life."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_afflict(perm: Permanent) -> bool:
    """Return True when the permanent has afflict."""
    return has_keyword(perm, 'Afflict')


def apply_afflict_on_attack(game: GameState, attacker: Permanent) -> str | None:
    """Defending player loses 1 life when a creature with afflict attacks."""
    if not has_afflict(attacker):
        return None
    defender = 1 - attacker.controller_idx
    game.players[defender].life -= 1
    game.mark_player_was_dealt_damage(defender)
    return f"afflict: P{defender + 1} loses 1 life"
