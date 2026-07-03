"""Tests for colored mana payment when casting spells (Phase H)."""

from __future__ import annotations

from engine.cards.oracle_parse import is_affordable
from engine.game import create_game
from engine.game.mana_payment import can_pay_cast_mana, pay_cast_mana
from tests.conftest import _CardStats, add_to_hand, fresh_game, make_card, make_deck
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
    assert game.state.stack.is_empty is False
