"""Unit tests for ability_other batch 2: fabricate, devour, ascend, dash."""

from __future__ import annotations

from engine.abilities.keywords.other.dash import apply_dash_etb, return_dash_creatures_to_hand
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_fabricate_puts_counters_by_default():
    """Fabricate without artifact wording adds +1/+1 counters."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Welder', 2, 2, oracle='Fabricate 2'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, perm)
    assert any('fabricated' in detail for detail in details)
    assert perm.counters.get('+1/+1') == 2


def test_devour_sacrifices_for_counters():
    """Devour sacrifices other creatures and adds counters."""
    game = fresh_game()
    host = place_on_battlefield(
        make_creature('Dragon', 4, 4, oracle='Devour 2'),
        0,
        game.zones,
    )
    place_on_battlefield(make_creature('Food', 1, 1), 0, game.zones)
    place_on_battlefield(make_creature('Fodder', 1, 1), 0, game.zones)
    details = apply_etb_other_abilities(game, host)
    assert any('devoured' in detail for detail in details)
    assert host.counters.get('+1/+1') == 2


def test_ascend_at_ten_permanents():
    """Ascend grants City's Blessing at ten permanents."""
    game = fresh_game()
    for idx in range(9):
        place_on_battlefield(make_creature(f'P{idx}', 1, 1), 0, game.zones)
    tenth = place_on_battlefield(make_creature('Ascendant', 1, 1, oracle='Ascend'), 0, game.zones)
    apply_etb_other_abilities(game, tenth)
    assert game.players[0].ascended


def test_dash_creature_returns_to_hand_at_end_of_turn():
    """Dashed creatures return to hand at end of turn."""
    game = fresh_game()
    card = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature('Sprinter', 3, 3, oracle='Dash {1}{R}'),
    )
    perm = game.zones.enter_battlefield(card, 0, 'dash', Zone.HAND)
    perm.counters['dash'] = 1
    perm.sick = False
    apply_dash_etb(perm)
    assert perm.counters.get('dash') == 1
    assert not perm.sick
    details = return_dash_creatures_to_hand(game, 0)
    assert details
    assert len(game.zones.player_zones[0].hand) == 1
    assert len(game.zones.battlefield) == 0
