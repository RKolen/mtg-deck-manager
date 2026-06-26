"""Firebending: add red mana until end of combat when this attacks (CR 702.189)."""

from __future__ import annotations

import re

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState

_FIREBENDING_RE = re.compile(r'firebending\s+(\d+)', re.IGNORECASE)


def has_firebending(perm: Permanent) -> bool:
    """Return True when the permanent has firebending."""
    return has_keyword(perm, 'Firebending') or bool(
        _FIREBENDING_RE.search(perm.oracle_text or '')
    )


def firebending_amount(oracle_text: str) -> int:
    """Parse N from 'Firebending N'."""
    match = _FIREBENDING_RE.search(oracle_text or '')
    if match is None:
        return 1
    return int(match.group(1))


def apply_firebending_on_attack(game: GameState, attacker: Permanent) -> str | None:
    """Add red mana that lasts until end of combat."""
    if not has_firebending(attacker):
        return None
    amount = firebending_amount(attacker.oracle_text or '')
    player = game.players[attacker.controller_idx]
    player.mana_pool.add_color('R', amount)
    player.firebending_red += amount
    return f"firebending {attacker.name} (+{amount}R until end of combat)"


def clear_firebending_mana(game: GameState, player_idx: int) -> list[str]:
    """Remove firebending mana at end of combat."""
    player = game.players[player_idx]
    amount = player.firebending_red
    if amount <= 0:
        return []
    removed = 0
    kept: list = []
    for mana in player.mana_pool.pool:
        if mana.color == 'R' and removed < amount:
            removed += 1
            continue
        kept.append(mana)
    player.mana_pool.pool = kept
    player.firebending_red = 0
    return [f"firebending mana cleared ({removed}R)"]
