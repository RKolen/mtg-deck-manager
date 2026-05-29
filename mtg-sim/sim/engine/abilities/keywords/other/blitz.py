"""Blitz: haste and sacrifice at end of turn."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_blitz(perm: Permanent) -> bool:
    """Return True when the permanent has blitz."""
    return has_keyword(perm, 'Blitz') or perm.counters.get('blitz', 0) > 0


def apply_blitz_etb(permanent: Permanent) -> str | None:
    """Confirm blitz haste when the creature was cast for blitz."""
    if not permanent.counters.get('blitz'):
        return None
    permanent.sick = False
    return f"{permanent.name} blitzed (haste)"


def sacrifice_blitz_creatures(game: GameState, player_idx: int) -> list[str]:
    """Sacrifice blitzed creatures at end of turn."""
    details: list[str] = []
    for perm in list(game.zones.battlefield):
        if perm.controller_idx != player_idx:
            continue
        if not perm.counters.pop('blitz', 0):
            continue
        game.zones.leave_battlefield(perm, Zone.GRAVEYARD, 'blitz', game)
        details.append(f"{perm.name} sacrificed (blitz)")
    return details
