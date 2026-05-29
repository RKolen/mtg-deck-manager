"""Embalm: activate from hand to create an exiled Zombie token copy (simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.abilities.keywords.other.embalm_token import create_embalm_token_in_exile
from engine.core.mana import ManaCost

_EMBALM_COST_RE = re.compile(
    r'embalm\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_embalm(card: CardInfo) -> bool:
    """Return True when the creature has embalm."""
    if not card.is_creature:
        return False
    return has_registered_keyword(card.oracle_text, 'Embalm') or bool(
        _EMBALM_COST_RE.search(card.oracle_text or '')
    )


def embalm_cost(card: CardInfo) -> ManaCost | None:
    """Parse the embalm cost from oracle text."""
    match = _EMBALM_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def embalm_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the embalm cost."""
    return alt_cost_mana_needed(embalm_cost(card), card)


def can_embalm(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return True when embalm may be activated in the current timing window."""
    if not has_embalm(card):
        return False
    return phase in ('main1', 'main2') and stack_is_empty


__all__ = [
    'can_embalm',
    'create_embalm_token_in_exile',
    'embalm_cost',
    'embalm_mana_needed',
    'has_embalm',
]
