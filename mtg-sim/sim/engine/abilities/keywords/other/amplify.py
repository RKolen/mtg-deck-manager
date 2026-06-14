"""Amplify: ETB +1/+1 counters for each hand creature sharing a creature type (simplified)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.core.game_object import CardObject, Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_AMPLIFY_RE = re.compile(r'amplify\s+(\w+|\d+)', re.IGNORECASE)
_SUBTYPE_RE = re.compile(r'creature\s*[—–-]\s*([^\n]+)', re.IGNORECASE)


def has_amplify(perm: Permanent) -> bool:
    """Return True when the permanent has amplify."""
    return has_keyword(perm, 'Amplify')


def amplify_amount(oracle_text: str) -> int:
    """Parse N from 'Amplify N'."""
    match = _AMPLIFY_RE.search(oracle_text or '')
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def _creature_subtypes(type_line: str) -> set[str]:
    match = _SUBTYPE_RE.search(type_line or '')
    if match is None:
        return set()
    return {part.strip().lower() for part in match.group(1).split() if part.strip()}


def _shares_creature_type(a: str, b: str) -> bool:
    left = _creature_subtypes(a)
    right = _creature_subtypes(b)
    return bool(left and right and left & right)


def _matching_hand_creature_count(
    game: GameState,
    controller_idx: int,
    type_line: str,
) -> int:
    hand = game.zones.player_zones[controller_idx].hand
    count = 0
    for card in hand:
        if not isinstance(card, CardObject):
            continue
        info = card.card_info
        if info is None or not info.is_creature:
            continue
        if _shares_creature_type(type_line, info.type_line):
            count += 1
    return count


def apply_amplify_etb(game: GameState, permanent: Permanent) -> str | None:
    """Put amplify counters on ETB based on matching creatures in hand."""
    if not has_amplify(permanent):
        return None
    matches = _matching_hand_creature_count(
        game,
        permanent.controller_idx,
        permanent.type_line,
    )
    if matches <= 0:
        return f"amplify {permanent.name} (no matches)"
    amount = amplify_amount(permanent.oracle_text) * matches
    put_plus_counters(permanent, amount)
    return f"amplify +{amount}/+{amount} on {permanent.name}"
