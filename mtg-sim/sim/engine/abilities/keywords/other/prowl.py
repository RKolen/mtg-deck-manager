"""Prowl: unblockable when cast from graveyard with shared creature type (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject, Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_prowl(perm: Permanent) -> bool:
    """Return True when the permanent has prowl."""
    return has_keyword(perm, 'Prowl')


def has_prowl_card(card: CardInfo) -> bool:
    """Return True when the card has prowl."""
    return has_registered_keyword(card.oracle_text, 'Prowl')


def _creature_types(type_line: str) -> set[str]:
    if '—' not in type_line:
        return set()
    subtype_part = type_line.split('—', 1)[1]
    return {part.strip().lower() for part in subtype_part.split() if part.strip()}


def prowl_unblockable(attacker: Permanent, game: GameState) -> bool:
    """Return True when prowl makes the attacker unblockable (simplified)."""
    if not has_prowl(attacker):
        return False
    if attacker.counters.get('prowl_unblocked'):
        return True
    attacker_types = _creature_types(attacker.type_line)
    if not attacker_types:
        return False
    graveyard = game.zones.player_zones[attacker.controller_idx].graveyard
    for card in graveyard:
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        if not card.card_info.is_creature:
            continue
        if attacker_types & _creature_types(card.card_info.type_line):
            return True
    return False


def mark_prowl_cast(permanent: Permanent) -> None:
    """Mark a permanent that entered with prowl satisfied."""
    permanent.counters['prowl_unblocked'] = 1
