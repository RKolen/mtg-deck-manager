"""Commander ninjutsu: ninjutsu from the command zone (CR 702.124j, simplified)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.activated._cost_keyword import (
    alt_cost_mana_value,
    has_cost_keyword,
    parse_alt_cost,
    timing_allows_hand_activation,
)
from engine.abilities.keywords.actions.targets import find_creature_by_uid
from engine.core.game_object import CardObject
from engine.core.zones import Zone, ZoneManager

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_COMMANDER_NINJUTSU_RE = re.compile(
    r'commander\s+ninjutsu\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_commander_ninjutsu(card: CardInfo) -> bool:
    """Return True when the card has commander ninjutsu."""
    return card.is_creature and has_cost_keyword(
        card,
        'Commander ninjutsu',
        _COMMANDER_NINJUTSU_RE,
    )


def commander_ninjutsu_mana_needed(card: CardInfo) -> int:
    """Return generic mana to pay commander ninjutsu."""
    if parse_alt_cost(card, _COMMANDER_NINJUTSU_RE) is None:
        return 0
    return alt_cost_mana_value(card, _COMMANDER_NINJUTSU_RE)


def can_commander_ninjutsu(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when commander ninjutsu may be used during combat."""
    if not has_commander_ninjutsu(card):
        return False
    return phase in ('attack', 'declare_blockers') or timing_allows_hand_activation(
        phase,
        stack_is_empty,
    )


def assign_commander(
    game: GameState,
    player_idx: int,
    commander: CardObject,
) -> None:
    """Place a commander in the command zone (simplified in-memory)."""
    game.players[player_idx].commander = commander


def apply_commander_ninjutsu(
    game: GameState,
    zones: ZoneManager,
    player_idx: int,
    attacker_uid: str | None,
) -> str | None:
    """Return an unblocked attacker and put the commander onto the battlefield."""
    commander = game.players[player_idx].commander
    if commander is None or commander.card_info is None:
        return None
    if not has_commander_ninjutsu(commander.card_info):
        return None
    attacker = find_creature_by_uid(zones, attacker_uid)
    if attacker is None or attacker.controller_idx != player_idx:
        return None
    zones.leave_battlefield(attacker, Zone.HAND, 'commander_ninjutsu', game)
    game.players[player_idx].commander = None
    ninja = zones.enter_battlefield(commander, player_idx, 'commander_ninjutsu')
    ninja.tapped = False
    ninja.sick = False
    return f"commander ninjutsu {ninja.name} replaced {attacker.name}"
