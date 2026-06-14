"""Hideaway: ETB exile cards from library; cast later for hideaway cost (simplified)."""

from __future__ import annotations

import re

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import CardObject, Permanent
from engine.core.game_state import GameState

_HIDEAWAY_RE = re.compile(r'hideaway\s+(\w+|\d+)', re.IGNORECASE)
_HIDDEN_CARD_COUNTER = 'hideaway_card_obj'


def has_hideaway(perm: Permanent) -> bool:
    """Return True when the permanent has hideaway."""
    return has_keyword(perm, 'Hideaway')


def hideaway_count(oracle_text: str) -> int:
    """Parse N from Hideaway N (default 4)."""
    match = _HIDEAWAY_RE.search(oracle_text)
    if match is None:
        return 4
    token = match.group(1)
    return int(token) if token.isdigit() else 4


def apply_hideaway_etb(game: GameState, permanent: Permanent) -> str | None:
    """Exile the top N cards and stash one under this permanent."""
    if not has_hideaway(permanent):
        return None
    player_idx = permanent.controller_idx
    library = game.zones.player_zones[player_idx].library
    count = hideaway_count(permanent.oracle_text)
    exiled: list[CardObject] = []
    for _ in range(min(count, len(library))):
        card = library.pop(0)
        if isinstance(card, CardObject):
            game.zones.player_zones[player_idx].exile.append(card)
            exiled.append(card)
    if not exiled:
        return f"hideaway {permanent.name} (empty library)"
    hidden = exiled[0]
    permanent.counters[_HIDDEN_CARD_COUNTER] = hidden.obj_id
    return f"hideaway {permanent.name} hid {hidden.card_info.name if hidden.card_info else 'card'}"
