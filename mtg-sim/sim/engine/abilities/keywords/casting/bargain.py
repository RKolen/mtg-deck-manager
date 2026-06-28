"""Bargain: sacrifice an artifact or discard a card as you cast (CR 702.136, simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.zones import Zone, ZoneManager


def has_bargain(card: CardInfo) -> bool:
    """Return True when the spell has bargain."""
    if card.is_creature or card.is_land:
        return False
    return has_registered_keyword(card.oracle_text, 'Bargain')


def has_bargain_card(card: CardInfo) -> bool:
    """Return True when the card has bargain."""
    return has_bargain(card)


def normalize_paid_bargain(card: CardInfo, paid_bargain: bool) -> bool:
    """Return whether this cast pays bargain."""
    return paid_bargain and has_bargain(card)


def bargain_sacrifice_error(
    zones: ZoneManager,
    player_idx: int,
    card: CardInfo,
    paid_bargain: bool,
    sacrifice_ids: list[int],
) -> str | None:
    """Return an error when bargain sacrifice is illegal."""
    if not normalize_paid_bargain(card, paid_bargain):
        return None
    if not sacrifice_ids:
        return f"{card.name} bargain requires sacrificing an artifact"
    perm = zones.find_permanent(sacrifice_ids[0])
    if perm is None:
        return "Bargain sacrifice not found"
    if perm.controller_idx != player_idx:
        return "Bargain may only sacrifice artifacts you control"
    if 'Artifact' not in perm.type_line:
        return f"{perm.name} is not an artifact"
    return None


def normalize_bargain_sacrifice_id(
    card: CardInfo,
    paid_bargain: bool,
    sacrifice_ids: list[int],
) -> int | None:
    """Return the permanent id to sacrifice for bargain, if any."""
    if not normalize_paid_bargain(card, paid_bargain) or not sacrifice_ids:
        return None
    return sacrifice_ids[0]


def sacrifice_for_bargain(
    zones: ZoneManager,
    sacrifice_id: int,
) -> Permanent:
    """Move the bargain sacrifice to the graveyard."""
    perm = zones.find_permanent(sacrifice_id)
    assert perm is not None
    zones.leave_battlefield(perm, Zone.GRAVEYARD, 'bargain')
    return perm


def bargain_draw_on_cast(card: CardInfo, paid_bargain: bool) -> bool:
    """Return True when bargain should draw a card on resolution."""
    if not normalize_paid_bargain(card, paid_bargain):
        return False
    return 'draw a card' in (card.oracle_text or '').lower()
