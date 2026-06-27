"""Unit tests for megamorph (batch 33)."""

from __future__ import annotations

from engine.abilities.keywords.other.megamorph import (
    apply_megamorph_turn_up,
    has_megamorph,
    megamorph_turn_up_mana_needed,
)
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_megamorph_turn_up_adds_counter():
    """Megamorph adds a +1/+1 counter when turned face up."""
    card = make_creature(
        'Scalebane',
        4,
        4,
        oracle='Megamorph {3}\nFlying',
    )
    assert has_megamorph(card)
    assert megamorph_turn_up_mana_needed(card) == 3
    game = fresh_game()
    perm = place_on_battlefield(card, 0, game.zones)
    perm.face_down = True
    detail = apply_megamorph_turn_up(game, perm)
    assert detail is not None
    assert not perm.face_down
    assert perm.counters.get('+1/+1', 0) == 1
