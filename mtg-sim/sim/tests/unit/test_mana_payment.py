"""Tests for colored mana payment when casting spells (Phase H)."""

from __future__ import annotations

from engine.abilities.activated.core import activation_mana_cost
from engine.cards.oracle_parse import is_affordable
from engine.core.game_object import CardObject
from engine.game import create_game
from engine.game.mana_payment import (
    can_pay_cast_mana,
    can_pay_mana_cost,
    pay_cast_mana,
    pay_mana_cost,
)
from tests.conftest import _CardStats, add_to_hand, fresh_game, make_card, make_creature, make_deck
from tests.conftest import make_instant, make_land, place_on_battlefield


def test_cannot_afford_red_spell_with_only_forest():
    """Red spells require a red mana source, not just any untapped land."""
    game = fresh_game()
    place_on_battlefield(make_land('Forest', 'G'), 0, game.zones)
    bolt = make_instant('Lightning Bolt', mana_cost='{R}', oracle='deals 3 damage')
    assert not is_affordable(bolt, 1, game.zones, 0)


def test_can_afford_red_spell_with_mountain():
    """A basic Mountain can pay for a one-red spell."""
    game = fresh_game()
    place_on_battlefield(make_land('Mountain', 'R'), 0, game.zones)
    bolt = make_instant('Lightning Bolt', mana_cost='{R}', oracle='deals 3 damage')
    assert is_affordable(bolt, 1, game.zones, 0)


def test_pay_cast_mana_taps_mountain_for_bolt():
    """Casting payment taps a Mountain and leaves the player able to resolve."""
    game = fresh_game()
    place_on_battlefield(make_land('Mountain', 'R'), 0, game.zones)
    bolt = make_instant('Lightning Bolt', mana_cost='{R}', oracle='deals 3 damage')
    assert pay_cast_mana(game, 0, bolt, 1) is True
    assert game.zones.battlefield[0].tapped is True


def test_dual_land_pays_blue_spell():
    """Two dual lands can pay a two-blue spell by choosing blue each time."""
    game = fresh_game()
    steam = make_card(
        'Steam Vents',
        type_line='Land — Island Mountain',
        oracle='({T}: Add {U} or {R}.)',
        stats=_CardStats(cmc=0.0, pt='0/0'),
    )
    place_on_battlefield(steam, 0, game.zones)
    counterspell = make_instant('Counterspell', mana_cost='{U}{U}', oracle='Counter target spell.')
    assert can_pay_cast_mana(game.zones, 0, counterspell, 2) is False
    place_on_battlefield(steam, 0, game.zones)
    assert can_pay_cast_mana(game.zones, 0, counterspell, 2) is True


def test_cast_shock_taps_mountain_for_red_mana():
    """Interactive cast path pays colored mana and puts the spell on the stack."""
    shock = make_instant('Shock', mana_cost='{R}', oracle='Shock deals 2 damage.')
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    add_to_hand(shock, 0, game.state.zones)
    hand_idx = len(game.state.zones.player_zones[0].hand) - 1
    place_on_battlefield(make_land('Mountain', 'R'), 0, game.state.zones)
    data = game.action_cast(hand_idx)
    assert 'error' not in data
    assert any(perm.tapped for perm in game.state.zones.battlefield)


def test_cannot_pay_red_activation_with_forest_only():
    """A {1}{R} activation needs a red source, not just any land."""
    game = fresh_game()
    place_on_battlefield(make_land('Forest', 'G'), 0, game.zones)
    cost = activation_mana_cost('{1}{R}')
    assert not can_pay_mana_cost(game.zones, 0, cost)


def test_pay_red_activation_with_mountain_and_forest():
    """Generic plus colored pips can be paid across two lands."""
    game = fresh_game()
    place_on_battlefield(make_land('Forest', 'G'), 0, game.zones)
    place_on_battlefield(make_land('Mountain', 'R'), 0, game.zones)
    cost = activation_mana_cost('{1}{R}')
    assert pay_mana_cost(game, 0, cost) is True
    tapped = [perm.tapped for perm in game.zones.battlefield]
    assert tapped.count(True) == 2


def test_cycle_colored_cost_requires_matching_mana():
    """Cycling {1}{R} fails with only a Forest and succeeds with Mountain + land."""
    cycler = make_instant('Street Wraith', oracle='Cycling {1}{R}')
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=cycler),
    ]
    place_on_battlefield(make_land('Forest', 'G'), 0, game.state.zones)
    data = game.action_cycle(0)
    assert 'error' in data
    place_on_battlefield(make_land('Mountain', 'R'), 0, game.state.zones)
    place_on_battlefield(make_land('Forest', 'G'), 0, game.state.zones)
    data = game.action_cycle(0)
    assert 'error' not in data
    assert len(game.state.zones.player_zones[0].graveyard) == 1


def test_equip_colored_cost_taps_lands():
    """Equip {R} taps a Mountain instead of any untapped land."""
    sword = make_card(
        'Fire Sword',
        type_line='Artifact — Equipment',
        oracle='Equipped creature gets +1/+0.\nEquip {R}',
        stats=_CardStats(cmc=1.0, pt='0/0'),
    )
    host = make_creature('Soldier', 1, 1)
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    equip_perm = place_on_battlefield(sword, 0, game.state.zones, sick=False)
    host_perm = place_on_battlefield(host, 0, game.state.zones, sick=False)
    place_on_battlefield(make_land('Forest', 'G'), 0, game.state.zones)
    data = game.action_activate(
        str(equip_perm.obj_id),
        0,
        host_uid=str(host_perm.obj_id),
    )
    assert 'error' in data
    place_on_battlefield(make_land('Mountain', 'R'), 0, game.state.zones)
    data = game.action_activate(
        str(equip_perm.obj_id),
        0,
        host_uid=str(host_perm.obj_id),
    )
    assert 'error' not in data
    assert equip_perm.attached_to == host_perm.obj_id
