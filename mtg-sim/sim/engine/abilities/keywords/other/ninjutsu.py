"""Ninjutsu: return an unblocked attacker and put this onto the battlefield attacking."""

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
from engine.core.zones import Zone, ZoneManager
from engine.core.zone_card_lookup import hand_card_with_info

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_NINJUTSU_RE = re.compile(
    r'ninjutsu\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_ninjutsu(card: CardInfo) -> bool:
    """Return True when the card has ninjutsu."""
    return card.is_creature and has_cost_keyword(card, 'Ninjutsu', _NINJUTSU_RE)


def ninjutsu_mana_needed(card: CardInfo) -> int:
    """Return generic mana to pay ninjutsu."""
    if parse_alt_cost(card, _NINJUTSU_RE) is None:
        return 0
    return alt_cost_mana_value(card, _NINJUTSU_RE)


def can_ninjutsu(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when ninjutsu may be used from hand during combat."""
    if not has_ninjutsu(card):
        return False
    return phase in ('attack', 'declare_blockers') or timing_allows_hand_activation(
        phase,
        stack_is_empty,
    )


def apply_ninjutsu(
    game: GameState,
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
    attacker_uid: str | None,
) -> str | None:
    """Return an unblocked attacker to hand and put the ninja onto the battlefield."""
    loaded = hand_card_with_info(zones, player_idx, hand_idx)
    if loaded is None:
        return None
    card, card_info = loaded
    if not has_ninjutsu(card_info):
        return None
    attacker = find_creature_by_uid(zones, attacker_uid)
    if attacker is None or attacker.controller_idx != player_idx:
        return None
    zones.leave_battlefield(attacker, Zone.HAND, 'ninjutsu', game)
    zones.player_zones[player_idx].hand.pop(hand_idx)
    ninja = zones.enter_battlefield(card, player_idx, 'ninjutsu', Zone.HAND)
    ninja.tapped = False
    ninja.sick = False
    return f"ninjutsu {ninja.name} replaced {attacker.name}"
