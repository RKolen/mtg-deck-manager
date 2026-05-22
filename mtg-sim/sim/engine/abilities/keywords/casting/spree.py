"""Spree: choose one or more additional costs and effects (CR 702.156)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.cards.oracle_parse import parse_damage, parse_draw
from engine.core.mana import ManaCost

_SPREE_OPTION_RE = re.compile(
    r'[•·]\s*((?:\{[^{}]+\})+)\s*[—–-]\s*([^\n•·]+)',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SpreeMode:
    """One spree bullet: additional cost and effect text."""

    mana_value: int
    effect: str


def has_spree(card: CardInfo) -> bool:
    """Return True when the card has spree."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'Spree') or 'spree' in text.lower()


def spree_modes(card: CardInfo) -> list[SpreeMode]:
    """Parse spree mode costs and effects from oracle text."""
    if not has_spree(card):
        return []
    parsed: list[SpreeMode] = []
    for match in _SPREE_OPTION_RE.finditer(card.oracle_text or ''):
        cost = ManaCost.parse(match.group(1))
        effect = match.group(2).strip()
        parsed.append(SpreeMode(cost.mana_value, effect))
    return parsed


def normalize_spree_modes(card: CardInfo, mode_indices: list[int]) -> tuple[int, ...]:
    """Return sorted unique legal spree mode indices."""
    if not mode_indices or not has_spree(card):
        return ()
    options = spree_modes(card)
    seen: set[int] = set()
    valid: list[int] = []
    for idx in mode_indices:
        if 0 <= idx < len(options) and idx not in seen:
            seen.add(idx)
            valid.append(idx)
    return tuple(sorted(valid))


def spree_selection_error(card: CardInfo, mode_indices: list[int]) -> str | None:
    """Return an error message when spree mode choices are illegal."""
    message: str | None = None
    if mode_indices and not has_spree(card):
        message = f"{card.name} does not have spree"
    elif has_spree(card) and not normalize_spree_modes(card, mode_indices):
        message = "Spree requires choosing at least one mode"
    return message


def spree_extra_mana(card: CardInfo, mode_indices: tuple[int, ...]) -> int:
    """Return additional generic mana owed for chosen spree modes."""
    options = spree_modes(card)
    return sum(options[idx].mana_value for idx in mode_indices if idx < len(options))


def spree_mode_draw(effect: str) -> int:
    """Return cards to draw for a spree effect line, or 0."""
    return parse_draw(effect)


def spree_mode_damage(effect: str) -> int:
    """Return damage dealt by a spree effect line, or 0."""
    return parse_damage(effect)


def spree_mode_is_destroy(effect: str) -> bool:
    """Return True when a spree effect line destroys a target."""
    return 'destroy target' in effect.lower()
