"""Battle cry: other attacking creatures get +1/+0 until end of turn (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_BATTLE_CRY_COUNTER = 'battle_cry'


def has_battle_cry(perm: Permanent) -> bool:
    """Return True when the permanent has battle cry."""
    return has_keyword(perm, 'Battle cry')


def apply_battle_cry_on_attack(
    game: GameState,
    attacker: Permanent,
    attacker_ids: list[str],
) -> str | None:
    """Grant +1/+0 to other attacking creatures you control."""
    if not has_battle_cry(attacker):
        return None
    boosted: list[str] = []
    for perm in game.zones.battlefield:
        if perm.controller_idx != attacker.controller_idx:
            continue
        if str(perm.obj_id) == str(attacker.obj_id):
            continue
        if str(perm.obj_id) not in attacker_ids:
            continue
        perm.counters[_BATTLE_CRY_COUNTER] = perm.counters.get(_BATTLE_CRY_COUNTER, 0) + 1
        boosted.append(perm.name)
    if not boosted:
        return f"battle cry from {attacker.name} (no other attackers)"
    return f"battle cry +1/+0 on {', '.join(boosted)}"


def clear_battle_cry_counters(permanent: Permanent) -> None:
    """Remove temporary battle cry power at end of turn."""
    permanent.counters.pop(_BATTLE_CRY_COUNTER, None)
