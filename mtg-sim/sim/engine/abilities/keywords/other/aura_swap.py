"""Aura swap: exchange this Aura with one in your hand (CR 702.65)."""

from __future__ import annotations

import re

from engine.abilities.keywords.other.enchant import can_enchant_target, has_enchant
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject, Permanent
from engine.core.game_state import GameState
from engine.core.mana import ManaCost
from engine.core.zones import Zone

_AURA_SWAP_RE = re.compile(
    r'aura swap\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_aura_swap(perm: Permanent) -> bool:
    """Return True when the permanent has aura swap."""
    oracle = perm.oracle_text or ''
    return has_registered_keyword(oracle, 'Aura Swap') or bool(
        _AURA_SWAP_RE.search(oracle)
    )


def aura_swap_cost(perm: Permanent) -> ManaCost | None:
    """Parse the aura swap activation cost from oracle text."""
    match = _AURA_SWAP_RE.search(perm.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def aura_swap_mana_needed(perm: Permanent) -> int:
    """Return generic mana to activate aura swap."""
    cost = aura_swap_cost(perm)
    if cost is None:
        return 0
    return cost.mana_value


def can_aura_swap(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when aura swap may be activated."""
    if not has_aura_swap(perm) or perm.controller_idx != controller_idx:
        return False
    if 'Aura' not in perm.type_line:
        return False
    return phase in ('main1', 'main2') and game.stack.is_empty


def apply_aura_swap(  # pylint: disable=too-many-return-statements
    game: GameState,
    perm: Permanent,
    hand_idx: int,
) -> str | None:
    """Exchange this Aura with an Aura card from hand."""
    if not has_aura_swap(perm) or perm.attached_to is None:
        return None
    host = game.zones.find_permanent(perm.attached_to)
    if host is None:
        return None
    hand = game.zones.player_zones[perm.controller_idx].hand
    if hand_idx < 0 or hand_idx >= len(hand):
        return None
    card = hand[hand_idx]
    if not isinstance(card, CardObject) or card.card_info is None:
        return None
    card_info = card.card_info
    if 'Aura' not in card_info.type_line or not has_enchant(card_info):
        return None
    if not can_enchant_target(card_info.oracle_text or '', host):
        return None
    perm_name = perm.name
    incoming_name = card_info.name
    host_id = host.obj_id
    controller_idx = perm.controller_idx
    game.zones.leave_battlefield(perm, Zone.HAND, 'aura_swap', game)
    hand.pop(hand_idx)
    new_perm = game.zones.enter_battlefield(card, controller_idx, 'aura_swap')
    new_perm.attached_to = host_id
    return f"aura swap {perm_name} for {incoming_name}"
