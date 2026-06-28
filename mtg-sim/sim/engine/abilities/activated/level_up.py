"""Level up: pay cost to put a level counter on this creature (CR 702.40, simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState
from engine.core.mana import ManaCost

_LEVEL_UP_RE = re.compile(
    r"level up\s*((?:\{[^}]+\})+)",
    re.IGNORECASE,
)
LEVEL_COUNTER = "level"


def has_level_up(perm: Permanent) -> bool:
    """Return True when the permanent has level up."""
    return has_registered_keyword(perm.oracle_text, "Level Up") or bool(
        _LEVEL_UP_RE.search(perm.oracle_text)
    )


def has_level_up_card(card: CardInfo) -> bool:
    """Return True when the card has level up."""
    oracle = card.oracle_text or ""
    return has_registered_keyword(oracle, "Level Up") or bool(_LEVEL_UP_RE.search(oracle))


def level_up_cost(perm: Permanent) -> ManaCost | None:
    """Parse the level up cost from oracle text."""
    match = _LEVEL_UP_RE.search(perm.oracle_text)
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def level_up_mana_needed(perm: Permanent) -> int:
    """Return generic mana lands to tap for a level up activation."""
    cost = level_up_cost(perm)
    if cost is None:
        return 0
    return cost.mana_value


def can_level_up(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when level up may be activated."""
    if not has_level_up(perm) or perm.controller_idx != controller_idx:
        return False
    if "Creature" not in perm.type_line:
        return False
    return phase in ("main1", "main2") and game.stack.is_empty


def apply_level_up(perm: Permanent) -> int:
    """Add a level counter after costs are paid."""
    perm.counters[LEVEL_COUNTER] = perm.counters.get(LEVEL_COUNTER, 0) + 1
    perm.counters["+1/+1"] = perm.counters.get("+1/+1", 0) + 1
    return perm.counters[LEVEL_COUNTER]
