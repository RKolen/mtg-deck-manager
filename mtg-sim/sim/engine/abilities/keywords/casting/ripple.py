"""Ripple: reveal library cards sharing a name when you cast this spell."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.game_state import GameState

_RIPPLE_RE = re.compile(r'ripple\s+(\w+|\d+)', re.IGNORECASE)
_REVEAL_DEPTH = 4


def has_ripple(card: CardInfo) -> bool:
    """Return True when the card has ripple."""
    return has_registered_keyword(card.oracle_text, 'Ripple') or bool(
        _RIPPLE_RE.search(card.oracle_text or '')
    )


def ripple_reveal_count(oracle_text: str) -> int:
    """Parse N from 'Ripple N'."""
    match = _RIPPLE_RE.search(oracle_text or '')
    if match is None:
        return _REVEAL_DEPTH
    token = match.group(1)
    return int(token) if token.isdigit() else _REVEAL_DEPTH


def apply_ripple_on_cast(game: GameState, controller_idx: int, card: CardInfo) -> str | None:
    """Count matching cards among the top of the library."""
    if not has_ripple(card):
        return None
    depth = ripple_reveal_count(card.oracle_text)
    library = game.zones.player_zones[controller_idx].library
    matches = 0
    for card_obj in library[:depth]:
        if not isinstance(card_obj, CardObject) or card_obj.card_info is None:
            continue
        if card_obj.card_info.name == card.name:
            matches += 1
    return f"ripple {card.name} ({matches} match(es) in top {depth})"
