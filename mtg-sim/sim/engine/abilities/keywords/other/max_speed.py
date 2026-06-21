"""Max speed: abilities active only when controller speed is 4 (CR 702.178)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_MAX_SPEED_GRANT_RE = re.compile(
    r'max speed\s*[—–-]\s*([^\n]+)',
    re.IGNORECASE,
)
_MAX_SPEED = 4


def has_max_speed_keyword(perm: Permanent) -> bool:
    """Return True when the permanent has a max speed ability line."""
    return has_registered_keyword(perm.oracle_text or '', 'Max speed') or bool(
        _MAX_SPEED_GRANT_RE.search(perm.oracle_text or '')
    )


def player_speed(game: GameState, player_idx: int) -> int:
    """Return the player's current speed (0 means no speed)."""
    return game.players[player_idx].speed


def has_max_speed(game: GameState, player_idx: int) -> bool:
    """Return True when the player's speed is 4."""
    return player_speed(game, player_idx) >= _MAX_SPEED


def _max_speed_grant_text(perm: Permanent) -> str:
    match = _MAX_SPEED_GRANT_RE.search(perm.oracle_text or '')
    return match.group(1).lower() if match is not None else ''


def max_speed_grants(perm: Permanent, game: GameState, needle: str) -> bool:
    """Return True when max speed grants an ability containing needle."""
    if not has_max_speed(game, perm.controller_idx):
        return False
    return needle.lower() in _max_speed_grant_text(perm)


def max_speed_grants_haste(perm: Permanent, game: GameState) -> bool:
    """Return True when max speed grants haste to this permanent."""
    return has_keyword(perm, 'Haste') or max_speed_grants(perm, game, 'haste')


def requires_max_speed_to_attack(perm: Permanent) -> bool:
    """Return True when the permanent cannot attack without max speed."""
    text = (perm.oracle_text or '').lower()
    return (
        "can't attack or block unless you have max speed" in text
        or "can't attack unless you have max speed" in text
    )


def max_speed_blocks_attack(perm: Permanent, game: GameState | None) -> bool:
    """Return True when max speed prevents this permanent from attacking."""
    if game is None or not requires_max_speed_to_attack(perm):
        return False
    return not has_max_speed(game, perm.controller_idx)
