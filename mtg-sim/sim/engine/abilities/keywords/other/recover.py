"""Recover: return this card from the graveyard at upkeep (simplified, no cost)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_recover(card: CardInfo) -> bool:
    """Return True when the card has recover."""
    return has_registered_keyword(card.oracle_text, 'Recover')


def resolve_recover_upkeep(game: GameState, player_idx: int) -> list[str]:
    """Return the first recover card from the graveyard to hand."""
    graveyard = game.zones.player_zones[player_idx].graveyard
    for idx, card in enumerate(graveyard):
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        if not has_recover(card.card_info):
            continue
        graveyard.pop(idx)
        game.zones.player_zones[player_idx].hand.append(card)
        return [f"recover returned {card.card_info.name}"]
    return []
