"""Conspire: pay extra mana for a copy when a creature shares a color (CR 702.78, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost
from engine.core.game_object import Permanent, TokenObject
from engine.core.zones import ZoneManager

_CONSPIRE_PAY_RE = re.compile(
    r'pay\s*((?:\{[^}]+\})+)\s+to\s+have\s+a\s+copy',
    re.IGNORECASE,
)


def has_conspire(card: CardInfo) -> bool:
    """Return True when the card has conspire."""
    return has_registered_keyword(card.oracle_text, 'Conspire') or bool(
        _CONSPIRE_PAY_RE.search(card.oracle_text or '')
    )


def conspire_cost(card: CardInfo) -> ManaCost | None:
    """Parse the conspire payment from oracle reminder text."""
    match = _CONSPIRE_PAY_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def conspire_extra_mana(card: CardInfo, pay_conspire: bool) -> int:
    """Return additional generic mana owed when conspire is paid."""
    if not normalize_paid_conspire(card, pay_conspire):
        return 0
    cost = conspire_cost(card)
    return cost.mana_value if cost is not None else 2


def normalize_paid_conspire(card: CardInfo, pay_conspire: bool) -> bool:
    """Return whether conspire is paid for this cast."""
    if not pay_conspire:
        return False
    return has_conspire(card)


_COLOR_SYMBOL_RE = re.compile(r'\{([WUBRG])\}', re.IGNORECASE)


def spell_color_set(card: CardInfo) -> set[str]:
    """Return colors parsed from the spell's mana cost (simplified)."""
    text = card.mana_cost or ''
    return {match.group(1).upper() for match in _COLOR_SYMBOL_RE.finditer(text)}


def _permanent_color_set(perm: Permanent) -> set[str]:
    if perm.card_info is not None:
        return spell_color_set(perm.card_info)
    if isinstance(perm.source, TokenObject):
        return {color.upper() for color in (perm.source.colors or []) if color}
    return set()


def conspire_color_match(
    card: CardInfo,
    zones: ZoneManager,
    player_idx: int,
) -> bool:
    """Return True when a creature you control shares a color with the spell."""
    colors = spell_color_set(card)
    if not colors:
        return False
    for perm in zones.battlefield:
        if perm.controller_idx != player_idx:
            continue
        if 'Creature' not in perm.type_line:
            continue
        if colors & _permanent_color_set(perm):
            return True
    return False


def conspire_error(
    card: CardInfo,
    pay_conspire: bool,
    zones: ZoneManager,
    player_idx: int,
) -> str | None:
    """Return an error when conspire is illegal for this cast."""
    if not pay_conspire:
        return None
    if not has_conspire(card):
        return f"{card.name} does not have conspire"
    if not conspire_color_match(card, zones, player_idx):
        return "Conspire requires a creature that shares a color with this spell"
    return None


def supports_conspire_copies(card: CardInfo) -> bool:
    """Return True when a conspire copy is modeled for this spell."""
    return has_conspire(card) and not card.is_creature
