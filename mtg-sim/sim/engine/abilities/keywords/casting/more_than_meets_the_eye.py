"""More Than Meets the Eye: cast converted for an alternate cost (CR 702.162)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost

_MTME_RE = re.compile(
    r'more than meets the eye\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_CONVERTED = 'converted'


def has_more_than_meets_the_eye(card: CardInfo) -> bool:
    """Return True when the card has More Than Meets the Eye."""
    text = card.oracle_text or ''
    return has_registered_keyword(text, 'More Than Meets the Eye') or bool(
        _MTME_RE.search(text)
    )


def more_than_meets_the_eye_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the converted cast cost."""
    match = _MTME_RE.search(card.oracle_text or '')
    if match is None:
        return alt_cost_mana_needed(None, card)
    cost = ManaCost.parse(match.group(1))
    return alt_cost_mana_needed(cost, card)


def normalize_more_than_meets_the_eye_cast(
    card: CardInfo,
    cast_converted: bool,
) -> bool:
    """Return whether this cast uses the converted side."""
    return cast_converted and has_more_than_meets_the_eye(card)


def apply_converted_on_etb(permanent: Permanent) -> str | None:
    """Mark a permanent that entered converted."""
    permanent.counters[_CONVERTED] = 1
    return f"converted {permanent.name}"


def is_converted(perm: Permanent) -> bool:
    """Return True when the permanent entered via More Than Meets the Eye."""
    return perm.counters.get(_CONVERTED, 0) > 0
