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


def _prowl_graveyard_satisfied(permanent: Permanent, game: GameState) -> bool:
    """Return True when the graveyard satisfies prowl's creature-type requirement."""
    attacker_types = _creature_types(permanent.type_line)
    if not attacker_types:
        return False
    graveyard = game.zones.player_zones[permanent.controller_idx].graveyard
    for card in graveyard:
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        if not card.card_info.is_creature:
            continue
        if attacker_types & _creature_types(card.card_info.type_line):
            return True
    return False


def prowl_unblockable(attacker: Permanent, game: GameState) -> bool:
    """Return True when prowl makes the attacker unblockable (simplified)."""
    if not has_prowl(attacker):
        return False
    if attacker.counters.get('prowl_unblocked'):
        return True
    return _prowl_graveyard_satisfied(attacker, game)


def apply_prowl_on_etb(game: GameState, permanent: Permanent) -> str | None:
    """Mark prowl satisfied when a matching creature is in the graveyard."""
    if not has_prowl(permanent):
        return None
    if not _prowl_graveyard_satisfied(permanent, game):
        return None
    mark_prowl_cast(permanent)
    return f"prowl {permanent.name} (unblockable)"


def mark_prowl_cast(permanent: Permanent) -> None:
    """Mark a permanent that entered with prowl satisfied."""
    permanent.counters['prowl_unblocked'] = 1
