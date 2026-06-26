"""Enchant: aura targeting restriction (CR 303.4, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

_ENCHANT_RE = re.compile(r'enchant\s+([^\n.]+)', re.IGNORECASE)


def has_enchant(card: CardInfo) -> bool:
    """Return True when the card has enchant."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Enchant') or bool(_ENCHANT_RE.search(text))


def enchant_target_text(oracle_text: str) -> str:
    """Parse the enchant line target description."""
    match = _ENCHANT_RE.search(oracle_text or '')
    return match.group(1).strip().lower() if match is not None else ''


def can_enchant_target(oracle_text: str, host: Permanent) -> bool:  # pylint: disable=too-many-return-statements
    """Return True when host is a legal enchant target."""
    target = enchant_target_text(oracle_text)
    if not target:
        return False
    type_line = host.type_line
    name_lower = host.name.lower()
    if 'creature' in target:
        return 'Creature' in type_line
    if 'land' in target:
        return 'Land' in type_line
    if 'artifact' in target:
        return 'Artifact' in type_line
    if 'enchantment' in target:
        return 'Enchantment' in type_line
    if 'planeswalker' in target:
        return 'Planeswalker' in type_line
    if 'player' in target:
        return True
    return target in name_lower or target in type_line.lower()
