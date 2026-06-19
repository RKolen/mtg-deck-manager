"""Unit tests for rebound (batch 25)."""

from __future__ import annotations

from engine.abilities.keywords.casting.rebound import (
    exile_for_rebound,
    has_rebound,
    is_rebound_exiled_card,
    resolve_rebound_upkeep,
    should_exile_for_rebound,
)
from engine.core.game_object import CardObject, SpellOnStack
from tests.conftest import fresh_game, make_instant

_REBOUND_ORACLE = (
    'Rebound (If you cast this spell from your hand, exile it. '
    'At the beginning of your next upkeep, you may cast it from exile.)\n'
    'Draw a card.'
)


def test_rebound_exiles_and_returns_at_upkeep():
    """Rebound exiles on resolve and returns to hand at upkeep."""
    game = fresh_game()
    card_info = make_instant('Echo', cmc=2, oracle=_REBOUND_ORACLE)
    assert has_rebound(card_info)
    card = CardObject(controller_idx=0, owner_idx=0, card_info=card_info)
    spell = SpellOnStack(controller_idx=0, owner_idx=0, source=card)
    assert should_exile_for_rebound(spell, card_info)
    exile_for_rebound(game.zones, card)
    assert is_rebound_exiled_card(card)
    assert len(game.zones.player_zones[0].exile) == 1
    details = resolve_rebound_upkeep(game.zones, 0)
    assert details
    assert len(game.zones.player_zones[0].hand) == 1
    assert len(game.zones.player_zones[0].exile) == 0
