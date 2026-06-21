"""Splice: reveal an arcane from hand and pay its splice cost (simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.casting._hand_discard import discard_hand_card_name
from engine.core.game_object import CardObject
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager

_SPLICE_COST_RE = re.compile(
    r'splice\s*(?:onto\s+arcane\s*)?((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_splice(card: CardInfo) -> bool:
    """Return True when the card has splice onto arcane."""
    oracle = card.oracle_text or ''
    if 'Arcane' not in (card.type_line or ''):
        return False
    return has_registered_keyword(oracle, 'Splice') or bool(
        _SPLICE_COST_RE.search(oracle)
    )


def splice_cost(card: CardInfo) -> ManaCost | None:
    """Parse the splice cost from oracle text."""
    match = _SPLICE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def splice_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the splice cost."""
    return alt_cost_mana_needed(splice_cost(card), card)


def normalize_paid_splice(card: CardInfo, paid_splice: bool) -> bool:
    """Return whether this cast pays splice."""
    return paid_splice and has_splice(card)


def splice_hand_card_is_arcane(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int | None,
) -> bool:
    """Return True when the chosen hand card is an arcane spell."""
    if hand_idx is None:
        return False
    hand = zones.player_zones[player_idx].hand
    if hand_idx < 0 or hand_idx >= len(hand):
        return False
    card_obj = hand[hand_idx]
    if not isinstance(card_obj, CardObject) or card_obj.card_info is None:
        return False
    return 'Arcane' in (card_obj.card_info.type_line or '')


def splice_hand_error(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int | None,
    *,
    paid: bool,
) -> str | None:
    """Return an error when splice was announced without a valid arcane helper."""
    if not paid:
        return None
    if splice_hand_card_is_arcane(zones, player_idx, hand_idx):
        return None
    return "Splice requires an Arcane card from hand"


def discard_for_splice(
    zones: ZoneManager,
    player_idx: int,
    hand_idx: int | None,
) -> str | None:
    """Discard the spliced arcane card from hand."""
    if not splice_hand_card_is_arcane(zones, player_idx, hand_idx):
        return None
    return discard_hand_card_name(zones, player_idx, hand_idx)


def splice_mana_extra(card: CardInfo, paid_splice: bool) -> int:
    """Return extra mana when splice is paid on top of the spell's cost."""
    if not normalize_paid_splice(card, paid_splice):
        return 0
    mana, _life = splice_mana_needed(card)
    return mana
