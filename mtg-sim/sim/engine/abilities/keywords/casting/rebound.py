"""Rebound: exile on resolve from hand; return to hand at next upkeep."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject, SpellOnStack
from engine.core.game_object import spell_exiles_from_graveyard_cast
from engine.core.zones import ZoneManager

_REBOUND_MARKER = 'rebound'


def has_rebound(card: CardInfo) -> bool:
    """Return True when the instant or sorcery has rebound."""
    if not card.is_instant_or_sorcery:
        return False
    return has_registered_keyword(card.oracle_text, 'Rebound')


def should_exile_for_rebound(spell: SpellOnStack, card: CardInfo) -> bool:
    """Return True when a resolved spell should rebound-exile."""
    if not has_rebound(card) or spell_exiles_from_graveyard_cast(spell):
        return False
    return not spell.alternate.madness


def exile_for_rebound(zones: ZoneManager, card: CardObject) -> None:
    """Exile a spell that will rebound at the next upkeep."""
    card.exiled_cast_mode = _REBOUND_MARKER
    zones.player_zones[card.owner_idx].exile.append(card)


def is_rebound_exiled_card(card: CardObject) -> bool:
    """Return True when an exiled card is waiting to rebound."""
    return card.exiled_cast_mode == _REBOUND_MARKER


def resolve_rebound_upkeep(zones: ZoneManager, player_idx: int) -> list[str]:
    """Return the first rebound-exiled card to its owner's hand."""
    details: list[str] = []
    exile = zones.player_zones[player_idx].exile
    for idx, card in enumerate(exile):
        if not isinstance(card, CardObject) or not is_rebound_exiled_card(card):
            continue
        exile.pop(idx)
        card.exiled_cast_mode = None
        zones.player_zones[player_idx].hand.append(card)
        name = card.card_info.name if card.card_info is not None else 'card'
        details.append(f"rebound returned {name}")
        break
    return details
