"""Impending: pay to have a spell enter as a creature (simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.mana import ManaCost
from engine.core.zones import Zone, ZoneManager

_IMPENDING_RE = re.compile(
    r'impending\s+(\w+|\d+)\s*[—–-]\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_impending(card: CardInfo) -> bool:
    """Return True when the spell has impending."""
    if card.is_creature or card.is_land:
        return False
    return has_registered_keyword(card.oracle_text, 'Impending') or bool(
        _IMPENDING_RE.search(card.oracle_text or '')
    )


def impending_amount(card: CardInfo) -> int:
    """Return N from Impending N."""
    match = _IMPENDING_RE.search(card.oracle_text or '')
    if match is None:
        return 0
    token = match.group(1)
    return int(token) if token.isdigit() else 0


def impending_cost(card: CardInfo) -> ManaCost | None:
    """Parse the impending additional cost."""
    match = _IMPENDING_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(2))


def impending_mana_extra(card: CardInfo, paid_impending: bool) -> int:
    """Return extra mana when impending is paid."""
    if not normalize_paid_impending(card, paid_impending):
        return 0
    cost = impending_cost(card)
    return cost.mana_value if cost is not None else 0


def normalize_paid_impending(card: CardInfo, paid_impending: bool) -> bool:
    """Return whether this cast pays impending."""
    return paid_impending and has_impending(card)


def apply_impending_on_resolve(
    zones: ZoneManager,
    player_idx: int,
    card_obj: CardObject,
) -> str | None:
    """Enter the spell as an N/N creature instead of resolving normally."""
    card = card_obj.card_info
    if card is None:
        return None
    amount = impending_amount(card)
    if amount <= 0:
        amount = 1
    perm = zones.enter_battlefield(card_obj, player_idx, 'impending', Zone.STACK)
    put_plus_counters(perm, amount)
    perm.counters['impending'] = amount
    perm.sick = False
    return f"impending {card.name} {amount}/{amount}"
