"""Double team: conjure a duplicate on attack (digital, simplified)."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import CardObject, Permanent
from engine.core.game_state import GameState

_DOUBLE_TEAM_LOST = 'double_team_lost'


def has_double_team(perm: Permanent) -> bool:
    """Return True when the permanent has double team."""
    return has_keyword(perm, 'Double team')


def lost_double_team(perm: Permanent) -> bool:
    """Return True when double team has already triggered."""
    return perm.counters.get(_DOUBLE_TEAM_LOST, 0) > 0


def apply_double_team_on_attack(game: GameState, attacker: Permanent) -> str | None:
    """Conjure a duplicate into hand and remove double team from both copies."""
    if not has_double_team(attacker) or attacker.is_token or lost_double_team(attacker):
        return None
    card_info = attacker.card_info
    if card_info is None:
        return None
    duplicate = CardObject(
        controller_idx=attacker.controller_idx,
        owner_idx=attacker.owner_idx,
        card_info=card_info,
    )
    game.zones.player_zones[attacker.controller_idx].hand.append(duplicate)
    attacker.counters[_DOUBLE_TEAM_LOST] = 1
    return f"double team {attacker.name} (duplicate in hand)"
