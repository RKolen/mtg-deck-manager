"""Daybound and nightbound: toggle front/back face at upkeep (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_DAYBOUND_FRONT = 'daybound_front'


def has_daybound(perm: Permanent) -> bool:
    """Return True when the permanent has daybound."""
    return has_keyword(perm, 'Daybound')


def has_nightbound(perm: Permanent) -> bool:
    """Return True when the permanent has nightbound."""
    return has_keyword(perm, 'Nightbound')


def has_daybound_card(card: CardInfo) -> bool:
    """Return True when the card has daybound."""
    return has_registered_keyword(card.oracle_text, 'Daybound')


def has_nightbound_card(card: CardInfo) -> bool:
    """Return True when the card has nightbound."""
    return has_registered_keyword(card.oracle_text, 'Nightbound')


def is_daybound_front(perm: Permanent) -> bool:
    """Return True when a daybound/nightbound card is on its front face."""
    return perm.counters.get(_DAYBOUND_FRONT, 0) > 0


def apply_daybound_etb(permanent: Permanent) -> str | None:
    """Daybound cards enter on their daybound face."""
    if not has_daybound(permanent):
        return None
    permanent.counters[_DAYBOUND_FRONT] = 1
    return f"daybound {permanent.name} (front)"


def apply_nightbound_etb(permanent: Permanent) -> str | None:
    """Nightbound cards enter on their nightbound face."""
    if not has_nightbound(permanent):
        return None
    permanent.counters[_DAYBOUND_FRONT] = 0
    return f"nightbound {permanent.name} (back)"


def resolve_daybound_upkeep(game: GameState, player_idx: int) -> list[str]:
    """Toggle daybound/nightbound permanents at upkeep."""
    details: list[str] = []
    for perm in game.zones.battlefield:
        if perm.controller_idx != player_idx:
            continue
        if not has_daybound(perm) and not has_nightbound(perm):
            continue
        front = perm.counters.get(_DAYBOUND_FRONT, 0)
        perm.counters[_DAYBOUND_FRONT] = 0 if front else 1
        face = 'front' if perm.counters[_DAYBOUND_FRONT] else 'back'
        details.append(f"daybound {perm.name} ({face})")
    return details
