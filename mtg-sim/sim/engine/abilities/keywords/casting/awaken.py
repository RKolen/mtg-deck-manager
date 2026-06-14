"""Awaken: optional cost to animate a land as an N/N creature (CR 702.43, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject, Permanent
from engine.core.mana import ManaCost
from engine.core.zones import Zone, ZoneManager

_AWAKEN_RE = re.compile(
    r'awaken\s+(\w+|\d+)\s*[—–-]\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_awaken(card: CardInfo) -> bool:
    """Return True when the spell has awaken."""
    if card.is_land or card.is_creature:
        return False
    return has_registered_keyword(card.oracle_text, 'Awaken') or bool(
        _AWAKEN_RE.search(card.oracle_text or '')
    )


def awaken_amount(card: CardInfo) -> int:
    """Return N from Awaken N."""
    match = _AWAKEN_RE.search(card.oracle_text or '')
    if match is None:
        return 0
    token = match.group(1)
    return int(token) if token.isdigit() else 0


def awaken_cost(card: CardInfo) -> ManaCost | None:
    """Parse the awaken additional cost."""
    match = _AWAKEN_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(2))


def awaken_mana_extra(card: CardInfo, paid_awaken: bool) -> int:
    """Return extra mana when awaken is paid."""
    if not paid_awaken or not has_awaken(card):
        return 0
    cost = awaken_cost(card)
    return cost.mana_value if cost is not None else 0


def normalize_paid_awaken(card: CardInfo, paid_awaken: bool) -> bool:
    """Return whether this cast pays awaken."""
    return paid_awaken and has_awaken(card)


def awaken_land_error(
    zones: ZoneManager,
    player_idx: int,
    card: CardInfo,
    paid_awaken: bool,
    land_hand_idx: int | None,
) -> str | None:
    """Return an error when the awaken land choice is illegal."""
    if not normalize_paid_awaken(card, paid_awaken):
        if land_hand_idx is not None and has_awaken(card):
            return f"{card.name} was not cast with awaken"
        return None
    if land_hand_idx is None:
        return "Awaken requires choosing a land from your hand"
    hand = zones.player_zones[player_idx].hand
    if land_hand_idx < 0 or land_hand_idx >= len(hand):
        return "Awaken land hand index out of range"
    land = hand[land_hand_idx]
    if not isinstance(land, CardObject) or land.card_info is None or not land.card_info.is_land:
        return "Invalid awaken land" if not isinstance(land, CardObject) else (
            f"{land.card_info.name} is not a land"
            if land.card_info is not None
            else "Invalid awaken land"
        )
    return None


def apply_awaken_on_resolve(
    zones: ZoneManager,
    player_idx: int,
    card: CardInfo,
    land_hand_idx: int | None,
) -> str | None:
    """Put the chosen land onto the battlefield as an N/N creature with haste."""
    if land_hand_idx is None or not has_awaken(card):
        return None
    hand = zones.player_zones[player_idx].hand
    if land_hand_idx < 0 or land_hand_idx >= len(hand):
        return None
    land_card = hand.pop(land_hand_idx)
    if not isinstance(land_card, CardObject) or land_card.card_info is None:
        return None
    amount = awaken_amount(card)
    if amount <= 0:
        return None
    perm = zones.enter_battlefield(land_card, player_idx, 'awaken', Zone.HAND)
    put_plus_counters(perm, amount)
    perm.sick = False
    perm.counters['awaken'] = amount
    return f"awaken {perm.name} {amount}/{amount}"


def is_awakened_creature(perm: Permanent) -> bool:
    """Return True when a land is animated via awaken."""
    return perm.counters.get('awaken', 0) > 0
