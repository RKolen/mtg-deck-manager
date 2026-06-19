"""Unit tests for ripple (batch 26)."""

from __future__ import annotations

from engine.abilities.keywords.casting.ripple import (
    apply_ripple_on_cast,
    has_ripple,
)
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_instant

_RIPPLE_ORACLE = (
    'Ripple 4 (When you cast this spell, reveal the top four cards of your library. '
    'You may cast any revealed cards with the same name without paying their mana costs.)\n'
    'Draw a card.'
)


def test_ripple_counts_matching_library_cards():
    """Ripple counts how many matching cards are among the top of the library."""
    game = fresh_game()
    card = make_instant('Surge', cmc=2, oracle=_RIPPLE_ORACLE)
    assert has_ripple(card)
    for _ in range(2):
        game.zones.player_zones[0].library.append(
            CardObject(controller_idx=0, owner_idx=0, card_info=card),
        )
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Other', cmc=1)),
    )
    detail = apply_ripple_on_cast(game, 0, card)
    assert detail is not None
    assert '2 match' in detail
