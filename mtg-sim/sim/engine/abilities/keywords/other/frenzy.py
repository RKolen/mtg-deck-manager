"""Frenzy: draw when attacking unblocked (CR 702.40, simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_frenzy(perm: Permanent) -> bool:
    """Return True when the permanent has frenzy."""
    return has_keyword(perm, 'Frenzy')


def apply_frenzy_on_unblocked_attack(
    _game: GameState,
    attacker: Permanent,
    *,
    blocked: bool,
) -> str | None:
    """Draw a card when a frenzy creature attacks unblocked."""
    if blocked or not has_frenzy(attacker):
        return None
    oracle = (attacker.oracle_text or '').lower()
    if 'draw a card' not in oracle and 'draw two cards' not in oracle:
        return f"frenzy {attacker.name}"
    return f"frenzy {attacker.name} (draw)"
