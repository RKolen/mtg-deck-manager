"""Transmute: pay cost to search your library (simplified)."""

from __future__ import annotations

import re

from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject, Permanent
from engine.core.game_state import GameState
from engine.core.mana import ManaCost

_TRANSMUTE_RE = re.compile(
    r'transmute\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_TRANSMUTE_USED = 'transmute_used'


def has_transmute(perm: Permanent) -> bool:
    """Return True when the permanent has transmute."""
    oracle = perm.oracle_text or ''
    return has_registered_keyword(oracle, 'Transmute') or bool(
        _TRANSMUTE_RE.search(oracle)
    )


def transmute_cost(perm: Permanent) -> ManaCost | None:
    """Parse the transmute activation cost from oracle text."""
    match = _TRANSMUTE_RE.search(perm.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def transmute_mana_needed(perm: Permanent) -> int:
    """Return generic mana to activate transmute."""
    cost = transmute_cost(perm)
    if cost is None:
        return 0
    return cost.mana_value


def can_transmute(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when transmute may be activated."""
    if not has_transmute(perm) or perm.controller_idx != controller_idx:
        return False
    if perm.counters.get(_TRANSMUTE_USED):
        return False
    return phase in ('main1', 'main2') and game.stack.is_empty


def apply_transmute(game: GameState, perm: Permanent) -> str | None:
    """Search the top of the library and put one card into hand (simplified)."""
    if not has_transmute(perm):
        return None
    library = game.zones.player_zones[perm.controller_idx].library
    if not library:
        return f"transmute {perm.name} (library empty)"
    card = library.pop(0)
    if isinstance(card, CardObject):
        game.zones.player_zones[perm.controller_idx].hand.append(card)
        name = card.card_info.name if card.card_info else '?'
    else:
        name = '?'
    perm.counters[_TRANSMUTE_USED] = 1
    return f"transmute {perm.name} found {name}"


def clear_transmute_turn_marker(perm: Permanent) -> None:
    """Clear the once-per-turn transmute marker."""
    perm.counters.pop(_TRANSMUTE_USED, None)
