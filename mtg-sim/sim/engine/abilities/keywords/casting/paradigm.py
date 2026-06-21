"""Paradigm: exile on resolve; free cast each upkeep (simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject, SpellOnStack
from engine.core.game_object import spell_exiles_from_graveyard_cast
from engine.core.game_state import GameState
from engine.core.zones import ZoneManager

_PARADIGM_MARKER = 'paradigm'


def has_paradigm(card: CardInfo) -> bool:
    """Return True when the card has paradigm."""
    return has_registered_keyword(card.oracle_text, 'Paradigm')


def should_exile_for_paradigm(spell: SpellOnStack, card: CardInfo) -> bool:
    """Return True when a resolved spell should paradigm-exile."""
    if not has_paradigm(card) or spell_exiles_from_graveyard_cast(spell):
        return False
    return not spell.alternate.madness


def exile_for_paradigm(zones: ZoneManager, card: CardObject, game: GameState) -> None:
    """Exile a spell and register its name for future paradigm copies."""
    card.exiled_cast_mode = _PARADIGM_MARKER
    zones.player_zones[card.owner_idx].exile.append(card)
    card_info = card.card_info
    if card_info is None:
        return
    player = game.players[card.controller_idx]
    if card_info.name not in player.paradigm_spell_names:
        player.paradigm_spell_names.append(card_info.name)


def is_paradigm_exiled_card(card: CardObject) -> bool:
    """Return True when an exiled card is waiting for paradigm upkeep."""
    return card.exiled_cast_mode == _PARADIGM_MARKER


def resolve_paradigm_upkeep(game: GameState, player_idx: int) -> list[str]:
    """Log a free paradigm cast for each active spell name in exile."""
    details: list[str] = []
    player = game.players[player_idx]
    for name in player.paradigm_spell_names:
        for card in game.zones.player_zones[player_idx].exile:
            if not isinstance(card, CardObject) or not is_paradigm_exiled_card(card):
                continue
            card_info = card.card_info
            if card_info is not None and card_info.name == name:
                details.append(f"paradigm cast {name}")
                break
    return details
