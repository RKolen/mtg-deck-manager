"""Afterlife: create a Spirit token when this permanent dies."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords._token_factory import enter_token_from_blueprint
from engine.cards.oracle_parse import TokenBlueprint
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_AFTERLIFE_RE = re.compile(r'afterlife\s+(\w+|\d+)', re.IGNORECASE)

_SPIRIT = TokenBlueprint(
    name='Spirit',
    type_line='Creature — Spirit',
    power='1',
    toughness='1',
    colors=['B'],
    oracle_text='Flying',
)


def has_afterlife(perm: Permanent) -> bool:
    """Return True when the permanent has afterlife."""
    return has_keyword(perm, 'Afterlife')


def afterlife_token_count(oracle_text: str) -> int:
    """Parse N from 'Afterlife N'."""
    match = _AFTERLIFE_RE.search(oracle_text)
    if match is None:
        return 1
    token = match.group(1)
    return int(token) if token.isdigit() else 1


def apply_afterlife_on_die(game: GameState, dying: Permanent) -> str | None:
    """Create Spirit tokens when a permanent with afterlife dies."""
    if not has_afterlife(dying):
        return None
    count = afterlife_token_count(dying.oracle_text)
    for _ in range(count):
        enter_token_from_blueprint(
            game.zones,
            dying.controller_idx,
            _SPIRIT,
            cause='afterlife',
        )
    return f"afterlife created {count} Spirit token(s)"
