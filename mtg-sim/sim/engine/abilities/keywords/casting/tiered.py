"""Tiered: choose exactly one mode and pay its additional cost (CR 702.183)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.mana import ManaCost

_TIERED_OPTION_RE = re.compile(
    r'[•·]\s*((?:\{[^{}]+\})+)\s*[—–-]\s*([^\n•·]+)',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TieredMode:
    """One tiered bullet: additional cost and effect text."""

    mana_value: int
    effect: str


def has_tiered(card: CardInfo) -> bool:
    """Return True when the card has tiered."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Tiered') or 'tiered' in text.lower()


def tiered_modes(card: CardInfo) -> list[TieredMode]:
    """Parse tiered mode costs and effects from oracle text."""
    if not has_tiered(card):
        return []
    parsed: list[TieredMode] = []
    for match in _TIERED_OPTION_RE.finditer(card.oracle_text or ''):
        cost = ManaCost.parse(match.group(1))
        effect = match.group(2).strip()
        parsed.append(TieredMode(cost.mana_value, effect))
    return parsed


def normalize_tiered_mode(card: CardInfo, mode_index: int | None) -> int | None:
    """Return a legal tiered mode index, or None when tiered was not used."""
    if mode_index is None or not has_tiered(card):
        return None
    options = tiered_modes(card)
    if 0 <= mode_index < len(options):
        return mode_index
    return None


def tiered_selection_error(card: CardInfo, mode_index: int | None) -> str | None:
    """Return an error message when tiered mode choice is illegal."""
    if mode_index is not None and not has_tiered(card):
        return f"{card.name} does not have tiered"
    if has_tiered(card) and normalize_tiered_mode(card, mode_index) is None:
        return "Tiered requires choosing exactly one mode"
    return None


def tiered_extra_mana(card: CardInfo, mode_index: int | None) -> int:
    """Return additional generic mana owed for the chosen tiered mode."""
    normalized = normalize_tiered_mode(card, mode_index)
    if normalized is None:
        return 0
    options = tiered_modes(card)
    return options[normalized].mana_value
