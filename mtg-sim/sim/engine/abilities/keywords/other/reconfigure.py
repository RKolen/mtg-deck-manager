"""Reconfigure: attach as Equipment or unattach to become a creature (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_RECONFIGURE_CREATURE = 'reconfigure_creature'


def has_reconfigure(perm: Permanent) -> bool:
    """Return True when the permanent has reconfigure."""
    return has_keyword(perm, 'Reconfigure')


def is_reconfigure_creature(perm: Permanent) -> bool:
    """Return True when a reconfigure permanent is in creature mode."""
    return perm.counters.get(_RECONFIGURE_CREATURE, 0) > 0


def can_reconfigure(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when reconfigure may be activated."""
    if not has_reconfigure(perm) or perm.controller_idx != controller_idx:
        return False
    return phase in ('main1', 'main2') and game.stack.is_empty


def apply_reconfigure(perm: Permanent) -> str | None:
    """Toggle between creature mode and equipment mode."""
    if not has_reconfigure(perm):
        return None
    if is_reconfigure_creature(perm):
        perm.counters.pop(_RECONFIGURE_CREATURE, None)
        perm.attached_to = None
        return f"reconfigure {perm.name} (equipment)"
    perm.counters[_RECONFIGURE_CREATURE] = 1
    perm.attached_to = None
    return f"reconfigure {perm.name} (creature)"
