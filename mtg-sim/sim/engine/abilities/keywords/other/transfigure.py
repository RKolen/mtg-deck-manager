"""Transfigure: sacrifice to search for a creature with the same mana value."""

from __future__ import annotations

import re

from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject, Permanent
from engine.core.game_state import GameState
from engine.core.mana import ManaCost
from engine.core.zones import Zone

_TRANSFIGURE_RE = re.compile(
    r'transfigure\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_transfigure(perm: Permanent) -> bool:
    """Return True when the permanent has transfigure."""
    oracle = perm.oracle_text or ''
    return has_registered_keyword(oracle, 'Transfigure') or bool(
        _TRANSFIGURE_RE.search(oracle)
    )


def transfigure_cost(perm: Permanent) -> ManaCost | None:
    """Parse the transfigure activation cost from oracle text."""
    match = _TRANSFIGURE_RE.search(perm.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def transfigure_mana_needed(perm: Permanent) -> int:
    """Return generic mana to activate transfigure."""
    cost = transfigure_cost(perm)
    if cost is None:
        return 0
    return cost.mana_value


def can_transfigure(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when transfigure may be activated."""
    if not has_transfigure(perm) or perm.controller_idx != controller_idx:
        return False
    return phase in ('main1', 'main2') and game.stack.is_empty


def apply_transfigure(game: GameState, perm: Permanent) -> str | None:
    """Sacrifice this creature and put a same-CMC creature from library into hand."""
    if not has_transfigure(perm):
        return None
    card_info = perm.card_info
    if card_info is None:
        return None
    target_cmc = int(card_info.cmc) if card_info.cmc == int(card_info.cmc) else int(card_info.cmc)
    controller_idx = perm.controller_idx
    perm_name = perm.name
    game.zones.leave_battlefield(perm, Zone.GRAVEYARD, 'transfigure', game)
    library = game.zones.player_zones[controller_idx].library
    found_name = '?'
    for idx, card in enumerate(library):
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        info = card.card_info
        if not info.is_creature:
            continue
        cmc = int(info.cmc) if info.cmc == int(info.cmc) else int(info.cmc)
        if cmc != target_cmc:
            continue
        library.pop(idx)
        game.zones.player_zones[controller_idx].hand.append(card)
        found_name = info.name
        break
    return f"transfigure {perm_name} found {found_name}"
