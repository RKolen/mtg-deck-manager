"""Toxic: combat damage to a player gives poison counters (CR 702.162b)."""

from __future__ import annotations

import re

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState

_TOXIC_RE = re.compile(r'toxic\s+(\w+|\d+)', re.IGNORECASE)


def has_toxic(perm: Permanent) -> bool:
    """Return True when the permanent has toxic."""
    text = perm.oracle_text or ''
    return has_keyword(perm, 'Toxic') or has_registered_keyword(text, 'Toxic')


def toxic_amount(oracle_text: str) -> int:
    """Parse N from 'Toxic N'."""
    match = _TOXIC_RE.search(oracle_text or '')
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_toxic_on_player_damage(
    game: GameState,
    attacker: Permanent,
    damage: int,
    damaged_player_idx: int,
) -> str | None:
    """Give the damaged player poison counters equal to toxic."""
    if damage <= 0 or not has_toxic(attacker):
        return None
    amount = toxic_amount(attacker.oracle_text or '')
    player = game.players[damaged_player_idx]
    player.poison += amount
    return f"toxic {attacker.name} (+{amount} poison)"
