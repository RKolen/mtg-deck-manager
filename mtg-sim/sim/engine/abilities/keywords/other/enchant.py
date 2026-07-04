"""Enchant: aura targeting restriction (CR 303.4, simplified)."""

from __future__ import annotations

import re
from collections.abc import Callable

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

_ENCHANT_RE = re.compile(r'enchant\s+([^\n.]+)', re.IGNORECASE)

_EnchantPredicate = Callable[[str, str], bool]


def _type_has_creature(type_line: str, _name_lower: str) -> bool:
    return 'Creature' in type_line


def _type_has_land(type_line: str, _name_lower: str) -> bool:
    return 'Land' in type_line


def _type_has_artifact(type_line: str, _name_lower: str) -> bool:
    return 'Artifact' in type_line


def _type_has_enchantment(type_line: str, _name_lower: str) -> bool:
    return 'Enchantment' in type_line


def _type_has_planeswalker(type_line: str, _name_lower: str) -> bool:
    return 'Planeswalker' in type_line


def _always_player(_type_line: str, _name_lower: str) -> bool:
    return True


_ENCHANT_PREDICATES: tuple[tuple[str, _EnchantPredicate], ...] = (
    ('creature', _type_has_creature),
    ('land', _type_has_land),
    ('artifact', _type_has_artifact),
    ('enchantment', _type_has_enchantment),
    ('planeswalker', _type_has_planeswalker),
    ('player', _always_player),
)


def has_enchant(card: CardInfo) -> bool:
    """Return True when the card has enchant."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Enchant') or bool(_ENCHANT_RE.search(text))


def enchant_target_text(oracle_text: str) -> str:
    """Parse the enchant line target description."""
    match = _ENCHANT_RE.search(oracle_text or '')
    return match.group(1).strip().lower() if match is not None else ''


def can_enchant_target(oracle_text: str, host: Permanent) -> bool:
    """Return True when host is a legal enchant target."""
    target = enchant_target_text(oracle_text)
    if not target:
        return False
    type_line = host.type_line
    name_lower = host.name.lower()
    for keyword, predicate in _ENCHANT_PREDICATES:
        if keyword in target:
            return predicate(type_line, name_lower)
    return target in name_lower or target in type_line.lower()
