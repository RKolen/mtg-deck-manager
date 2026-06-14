"""Epic: cast from graveyard without paying mana at upkeep (simplified)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.zones import Zone

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_epic(card: CardInfo) -> bool:
    """Return True when the card has epic."""
    return has_registered_keyword(card.oracle_text, 'Epic')


def resolve_epic_upkeep(game: GameState, player_idx: int) -> list[str]:
    """Cast the first epic card from the graveyard without paying mana."""
    graveyard = game.zones.player_zones[player_idx].graveyard
    for idx, card in enumerate(graveyard):
        if not isinstance(card, CardObject) or card.card_info is None:
            continue
        card_info = card.card_info
        if not has_epic(card_info):
            continue
        graveyard.pop(idx)
        if card_info.is_creature:
            game.zones.enter_battlefield(card, player_idx, 'epic', Zone.GRAVEYARD)
            return [f"epic cast {card_info.name}"]
        game.zones.player_zones[player_idx].hand.append(card)
        return [f"epic returned {card_info.name} to hand"]
    return []
