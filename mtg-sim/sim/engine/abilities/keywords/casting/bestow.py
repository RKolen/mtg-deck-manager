"""Bestow: cast a creature for its bestow cost as an Aura on a creature (CR 702.103)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager

_BESTOW_COST_RE = re.compile(
    r'bestow\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_bestow(card: CardInfo) -> bool:
    """Return True when the creature may be cast for its bestow cost."""
    if not card.is_creature:
        return False
    return has_registered_keyword(card.oracle_text, 'Bestow') or bool(
        _BESTOW_COST_RE.search(card.oracle_text or '')
    )


def has_bestow_card(card: CardInfo) -> bool:
    """Return True when the card has bestow."""
    return has_bestow(card)


def bestow_cost(card: CardInfo) -> ManaCost | None:
    """Parse the bestow alternate cost from oracle text."""
    match = _BESTOW_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def bestow_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the bestow cost instead of the mana cost."""
    return alt_cost_mana_needed(bestow_cost(card), card)


def normalize_bestow(card: CardInfo, bestow_target_uid: str | None) -> bool:
    """Return whether this cast uses bestow."""
    if not bestow_target_uid:
        return False
    return has_bestow(card)


def bestow_host_error(
    zones: ZoneManager,
    player_idx: int,
    bestow_target_uid: str | None,
) -> str | None:
    """Return an error message when the bestow host is illegal."""
    if not bestow_target_uid:
        return None
    try:
        host_id = int(bestow_target_uid)
    except ValueError:
        return "Invalid bestow target"
    host = zones.find_permanent(host_id)
    if host is None:
        return f"Bestow host {host_id} not found"
    if host.controller_idx != player_idx:
        return "Bestow may only enchant creatures you control"
    if 'Creature' not in host.type_line:
        return f"{host.name} is not a creature"
    return None
