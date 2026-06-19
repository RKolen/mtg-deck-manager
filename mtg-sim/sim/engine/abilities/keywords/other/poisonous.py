"""Poisonous: combat damage to a player gives poison counters."""

from __future__ import annotations

import re

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState

_POISONOUS_RE = re.compile(r'poisonous\s+(\w+|\d+)', re.IGNORECASE)


def has_poisonous(perm: Permanent) -> bool:
    """Return True when the permanent has poisonous."""
    return has_keyword(perm, 'Poisonous')


def poisonous_amount(oracle_text: str) -> int:
    """Parse N from 'Poisonous N'."""
    match = _POISONOUS_RE.search(oracle_text or '')
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_poisonous_on_player_damage(
    game: GameState,
    attacker: Permanent,
    damage: int,
    damaged_player_idx: int,
) -> str | None:
    """Give the damaged player poison counters."""
    if damage <= 0 or not has_poisonous(attacker):
        return None
    amount = poisonous_amount(attacker.oracle_text)
    player = game.players[damaged_player_idx]
    player.poison += amount
    return f"poisonous {attacker.name} (+{amount} poison)"
