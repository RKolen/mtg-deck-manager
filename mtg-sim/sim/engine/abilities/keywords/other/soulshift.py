"""Soulshift: return a creature card from graveyard to hand on ETB."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import CardObject, Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_SOULSHIFT_RE = re.compile(r'soulshift\s+(\w+|\d+)', re.IGNORECASE)


def has_soulshift(perm: Permanent) -> bool:
    """Return True when the permanent has soulshift."""
    return has_keyword(perm, 'Soulshift')


def soulshift_amount(oracle_text: str) -> int:
    """Parse N from 'Soulshift N'."""
    match = _SOULSHIFT_RE.search(oracle_text or '')
    if match is None:
        return 0
    token = match.group(1)
    return int(token) if token.isdigit() else 0


def apply_soulshift_etb(game: GameState, permanent: Permanent) -> str | None:
    """Return a creature card with CMC at most N from the graveyard to hand."""
    if not has_soulshift(permanent):
        return None
    limit = soulshift_amount(permanent.oracle_text)
    graveyard = game.zones.player_zones[permanent.controller_idx].graveyard
    for idx, card in enumerate(graveyard):
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        if not card.card_info.is_creature:
            continue
        cmc = int(card.card_info.cmc)
        if limit > 0 and not 0 < cmc <= limit:
            continue
        graveyard.pop(idx)
        game.zones.player_zones[permanent.controller_idx].hand.append(card)
        return f"soulshift returned {card.card_info.name}"
    return f"soulshift {permanent.name} (none)"
