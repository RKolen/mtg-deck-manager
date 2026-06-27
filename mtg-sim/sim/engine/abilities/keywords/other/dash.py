"""Dash: haste and return to hand at end of turn."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.casting.dash import has_dash as _has_dash_on_card
from engine.core.game_object import CardObject, Permanent
if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_dash(perm: Permanent) -> bool:
    """Return True when the permanent was cast for dash."""
    return has_keyword(perm, 'Dash') or perm.counters.get('dash', 0) > 0


def has_dash_card(card: CardInfo) -> bool:
    """Return True when the card may be cast for dash."""
    return _has_dash_on_card(card)


def apply_dash_etb(permanent: Permanent) -> str | None:
    """Confirm dash haste when the creature was cast for dash."""
    if not permanent.counters.get('dash'):
        return None
    permanent.sick = False
    return f"{permanent.name} dashed (haste)"


def return_dash_creatures_to_hand(game: GameState, player_idx: int) -> list[str]:
    """Return dashed creatures to their owner's hand at end of turn."""
    details: list[str] = []
    for perm in list(game.zones.battlefield):
        if perm.controller_idx != player_idx:
            continue
        if not perm.counters.pop('dash', 0):
            continue
        if not isinstance(perm.source, CardObject):
            continue
        card = perm.source
        if perm in game.zones.battlefield:
            game.zones.battlefield.remove(perm)
        game.zones.player_zones[player_idx].hand.append(card)
        details.append(f"{perm.name} returned (dash)")
    return details
