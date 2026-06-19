"""Provoke: creatures that can block this must do so."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.combat import can_block, legal_blocker
from engine.core.game_object import Permanent
from engine.core.game_state import GameState


def has_provoke(perm: Permanent) -> bool:
    """Return True when the permanent has provoke."""
    return has_keyword(perm, 'Provoke')


def assign_provoke_blocks(
    game: GameState,
    pending_blockers: dict[str, str],
    attacker_ids: list[str],
    defending_player_idx: int,
) -> list[str]:
    """Auto-assign blockers for unblocked provoke attackers when legal."""
    details: list[str] = []
    assigned_blockers = set(pending_blockers.keys())
    blocked_attackers = set(pending_blockers.values())
    for attacker_id in attacker_ids:
        if attacker_id in blocked_attackers:
            continue
        attacker = game.zones.find_permanent(int(attacker_id))
        if attacker is None or not has_provoke(attacker):
            continue
        for perm in game.zones.battlefield:
            if perm.controller_idx != defending_player_idx:
                continue
            blocker_uid = str(perm.obj_id)
            if blocker_uid in assigned_blockers:
                continue
            if not can_block(perm) or not legal_blocker(perm, attacker, game):
                continue
            pending_blockers[blocker_uid] = attacker_id
            assigned_blockers.add(blocker_uid)
            blocked_attackers.add(attacker_id)
            details.append(f"provoke {perm.name} blocks {attacker.name}")
            break
    return details
