"""Myriad: on attack, token copies attack each other opponent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent, TokenObject, effective_power, effective_toughness

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_myriad(perm: Permanent) -> bool:
    """Return True when the permanent has myriad."""
    return has_keyword(perm, 'Myriad')


def has_myriad_card(card: CardInfo) -> bool:
    """Return True when the card has myriad."""
    return has_registered_keyword(card.oracle_text, 'Myriad')


def apply_myriad_on_attack(
    game: GameState,
    attacker: Permanent,
    *,
    defending_player_idx: int,
) -> str | None:
    """Create tapped token copies attacking each opponent except the defender."""
    if not has_myriad(attacker):
        return None
    player_count = len(game.players)
    created: list[str] = []
    for opponent_idx in range(player_count):
        if opponent_idx == attacker.controller_idx:
            continue
        if opponent_idx == defending_player_idx:
            continue
        token = TokenObject(
            controller_idx=attacker.controller_idx,
            owner_idx=attacker.owner_idx,
            name=attacker.name,
            type_line=attacker.type_line,
            power=str(effective_power(attacker)),
            toughness=str(effective_toughness(attacker)),
            oracle_text=attacker.oracle_text,
            created_by_obj_id=attacker.obj_id,
        )
        perm = game.zones.enter_battlefield(token, attacker.controller_idx, 'myriad')
        perm.tapped = True
        perm.counters['myriad_attacking'] = opponent_idx + 1
        created.append(attacker.name)
    if not created:
        return None
    return f"myriad token(s) of {attacker.name} ({len(created)})"
