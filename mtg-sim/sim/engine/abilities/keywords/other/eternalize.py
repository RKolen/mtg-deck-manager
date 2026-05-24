"""Eternalize: exile from graveyard to create a token copy in exile."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.activated._cost_keyword import (
    alt_cost_mana_value,
    has_cost_keyword,
    parse_alt_cost,
    timing_allows_hand_activation,
)
from engine.core.game_object import CardObject, TokenObject
from engine.core.zones import ZoneManager

_ETERNALIZE_RE = re.compile(
    r'eternalize\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_eternalize_card(card: CardInfo) -> bool:
    """Return True when the card has eternalize."""
    return card.is_creature and has_cost_keyword(card, 'Eternalize', _ETERNALIZE_RE)


def eternalize_mana_needed(card: CardInfo) -> int:
    """Return generic mana to pay eternalize."""
    if parse_alt_cost(card, _ETERNALIZE_RE) is None:
        return 0
    return alt_cost_mana_value(card, _ETERNALIZE_RE)


def can_eternalize(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when eternalize may be activated from the graveyard."""
    if not has_eternalize_card(card):
        return False
    return timing_allows_hand_activation(phase, stack_is_empty)


def apply_eternalize_from_graveyard(
    zones: ZoneManager,
    player_idx: int,
    graveyard_idx: int,
) -> str | None:
    """Exile a creature from graveyard and create an eternalize token in exile."""
    graveyard = zones.player_zones[player_idx].graveyard
    if graveyard_idx < 0 or graveyard_idx >= len(graveyard):
        return None
    card = graveyard[graveyard_idx]
    if not isinstance(card, CardObject) or card.card_info is None:
        return None
    card_info = card.card_info
    if not has_eternalize_card(card_info):
        return None
    zones.exile_from_graveyard(card, player_idx)
    token = TokenObject(
        controller_idx=player_idx,
        owner_idx=player_idx,
        name=f"{card_info.name} Token",
        type_line='Creature — Zombie',
        colors=['W'],
        power=str(card_info.numeric_power),
        toughness=str(card_info.numeric_toughness),
        oracle_text='',
        created_by_obj_id=card.obj_id,
    )
    zones.player_zones[player_idx].exile.append(token)
    return f"eternalized {card_info.name} (exile token)"
