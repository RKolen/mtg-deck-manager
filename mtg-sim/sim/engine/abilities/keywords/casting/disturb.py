"""Disturb: cast a creature from the graveyard for its disturb cost."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting._timing import INSTANT_SPEED_PHASES
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_DISTURB_RE = re.compile(
    r'disturb\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_disturb(card: CardInfo) -> bool:
    """Return True when the creature may be cast for its disturb cost."""
    if not card.is_creature:
        return False
    return has_registered_keyword(card.oracle_text, 'Disturb') or bool(
        _DISTURB_RE.search(card.oracle_text or '')
    )


def has_disturb_card(card: CardInfo) -> bool:
    """Return True when the card has disturb."""
    return has_disturb(card)


def disturb_cost(card: CardInfo) -> ManaCost | None:
    """Parse the disturb alternate cost from oracle text."""
    match = _DISTURB_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def disturb_mana_needed(card: CardInfo) -> int:
    """Return generic mana to pay the disturb cost."""
    cost = disturb_cost(card)
    if cost is None:
        return max(0, int(card.cmc) if card.cmc == int(card.cmc) else int(card.cmc))
    return cost.mana_value


def can_cast_via_disturb(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when disturb may be cast in the current timing window."""
    if not has_disturb(card):
        return False
    if phase in INSTANT_SPEED_PHASES:
        return True
    return phase in ('main1', 'main2') and stack_is_empty
