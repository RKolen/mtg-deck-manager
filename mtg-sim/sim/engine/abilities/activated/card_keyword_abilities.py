"""Cycling, channel, and unearth activated from hand or graveyard."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.activated._cost_keyword import (
    alt_cost_mana_value,
    discard_from_hand,
    has_cost_keyword,
    parse_alt_cost,
    timing_allows_hand_activation,
)
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.cards.oracle_parse import parse_damage, parse_draw
from engine.core.game_object import CardObject, Permanent
from engine.core.mana import ManaCost
from engine.core.zones import Zone, ZoneManager

_CYCLING_RE = re.compile(
    r"cycling\s*((?:\{[^}]+\})+)",
    re.IGNORECASE,
)
_CHANNEL_RE = re.compile(
    r"channel\s*[—–-]\s*((?:\{[^}]+\})+)",
    re.IGNORECASE,
)
_UNEARTH_RE = re.compile(
    r"unearth\s*((?:\{[^}]+\})+)",
    re.IGNORECASE,
)
_SCAVENGE_RE = re.compile(
    r"scavenge\s*((?:\{[^}]+\})+)",
    re.IGNORECASE,
)
UNEARTH_COUNTER = "unearth"


def has_cycling(card: CardInfo) -> bool:
    """Return True when the card has cycling."""
    return has_cost_keyword(card, "Cycling", _CYCLING_RE)


def has_cycling_card(card: CardInfo) -> bool:
    """Return True when the card has cycling."""
    return has_cycling(card)


def cycling_cost(card: CardInfo) -> ManaCost | None:
    """Parse the cycling cost from oracle text."""
    return parse_alt_cost(card, _CYCLING_RE)


def cycling_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for a cycling activation."""
    return alt_cost_mana_value(card, _CYCLING_RE)


def can_cycle(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when cycling may be activated from hand."""
    return has_cycling(card) and timing_allows_hand_activation(phase, stack_is_empty)


def cycle_from_hand(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
) -> CardObject:
    """Discard a card from hand for cycling (after costs are paid)."""
    return discard_from_hand(zones, player_idx, hand_idx)


def has_channel(card: CardInfo) -> bool:
    """Return True when the card has channel."""
    return has_cost_keyword(card, "Channel", _CHANNEL_RE)


def has_channel_card(card: CardInfo) -> bool:
    """Return True when the card has channel."""
    return has_channel(card)


def channel_cost(card: CardInfo) -> ManaCost | None:
    """Parse the channel cost from oracle text."""
    return parse_alt_cost(card, _CHANNEL_RE)


def channel_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for a channel activation."""
    return alt_cost_mana_value(card, _CHANNEL_RE)


def channel_effect(card: CardInfo) -> str:
    """Return the effect text after the channel cost (simplified parsing)."""
    text = card.oracle_text or ""
    lowered = text.lower()
    marker = "discard"
    idx = lowered.find(marker)
    if idx < 0:
        return ""
    segment = text[idx:]
    colon = segment.find(":")
    if colon < 0:
        return ""
    return segment[colon + 1:].strip()


def can_channel(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when channel may be activated from hand."""
    return has_channel(card) and timing_allows_hand_activation(phase, stack_is_empty)


def channel_draw(channel_effect_text: str) -> int:
    """Return cards to draw from a channel effect line."""
    return parse_draw(channel_effect_text)


def channel_damage(channel_effect_text: str) -> int:
    """Return damage from a channel effect line."""
    return parse_damage(channel_effect_text)


def discard_for_channel(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int,
) -> CardObject:
    """Discard a card from hand for channel (after costs are paid)."""
    return discard_from_hand(zones, player_idx, hand_idx)


def has_unearth(card: CardInfo) -> bool:
    """Return True when the card has unearth."""
    return has_cost_keyword(card, "Unearth", _UNEARTH_RE)


def has_unearth_card(card: CardInfo) -> bool:
    """Return True when the card has unearth."""
    return has_unearth(card)


def unearth_cost(card: CardInfo) -> ManaCost | None:
    """Parse the unearth cost from oracle text."""
    return parse_alt_cost(card, _UNEARTH_RE)


def unearth_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for an unearth activation."""
    return alt_cost_mana_value(card, _UNEARTH_RE)


def can_unearth(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when unearth may be activated from the graveyard."""
    return card.is_creature and has_unearth(card) and phase in ("main1", "main2") and stack_is_empty


def unearth_from_graveyard(
    zones: ZoneManager,
    player_idx: int,
    graveyard_idx: int,
) -> Permanent:
    """Move an unearthed creature onto the battlefield (after costs are paid)."""
    graveyard = zones.player_zones[player_idx].graveyard
    card = graveyard[graveyard_idx]
    assert isinstance(card, CardObject)
    perm = zones.enter_battlefield(card, player_idx, "unearth", Zone.GRAVEYARD)
    perm.sick = False
    perm.counters[UNEARTH_COUNTER] = 1
    return perm


def is_unearth_creature(perm: Permanent) -> bool:
    """Return True when a permanent was unearthed and should be exiled."""
    return perm.counters.get(UNEARTH_COUNTER, 0) > 0


def has_scavenge(card: CardInfo) -> bool:
    """Return True when the card has scavenge."""
    return card.is_creature and has_cost_keyword(card, "Scavenge", _SCAVENGE_RE)


def has_scavenge_card(card: CardInfo) -> bool:
    """Return True when the card has scavenge."""
    return has_scavenge(card)


def scavenge_cost(card: CardInfo) -> ManaCost | None:
    """Parse the scavenge cost from oracle text."""
    return parse_alt_cost(card, _SCAVENGE_RE)


def scavenge_mana_needed(card: CardInfo) -> int:
    """Return generic mana lands to tap for a scavenge activation."""
    return alt_cost_mana_value(card, _SCAVENGE_RE)


def scavenge_counter_amount(card: CardInfo) -> int:
    """Return +1/+1 counters to place from this card's power."""
    power = card.numeric_power
    if power is None:
        return 0
    return max(0, int(power))


def can_scavenge(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when scavenge may be activated from the graveyard."""
    return (
        card.is_creature
        and has_scavenge(card)
        and phase in ("main1", "main2")
        and stack_is_empty
    )


def scavenge_from_graveyard(
    zones: ZoneManager,
    player_idx: int,
    graveyard_idx: int,
    target: Permanent,
) -> tuple[str | None, str | None]:
    """Exile a scavenge card and put +1/+1 counters on a creature."""
    graveyard = zones.player_zones[player_idx].graveyard
    if graveyard_idx < 0 or graveyard_idx >= len(graveyard):
        return "Graveyard index out of range", None
    card = graveyard[graveyard_idx]
    if not isinstance(card, CardObject) or card.card_info is None:
        return "Invalid scavenge card", None
    card_info = card.card_info
    if not has_scavenge(card_info):
        return f"{card_info.name} does not have scavenge", None
    if 'Creature' not in target.type_line:
        return f"{target.name} is not a creature", None
    if target.controller_idx != player_idx:
        return "Scavenge may only target creatures you control", None
    amount = scavenge_counter_amount(card_info)
    zones.exile_from_graveyard(card, player_idx)
    if amount > 0:
        put_plus_counters(target, amount)
    return None, f"scavenged {card_info.name} onto {target.name} (+{amount}/+{amount})"
