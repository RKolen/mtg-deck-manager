"""Unit tests for keyword actions batch 7.

Destroy, Play, Abandon, Assemble, Reveal, and Double.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.specialty import (
    abandon_hand,
    apply_double_damage,
    assemble_legion,
    has_abandon,
    has_assemble,
    has_double,
    has_play,
    has_reveal,
    play_top_card,
    reveal_top_card,
)
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from tests.conftest import (
    add_to_hand,
    fresh_game,
    make_creature,
    make_instant,
    make_land,
    place_on_battlefield,
)


def test_destroy_action_sends_creature_to_graveyard():
    """Destroy keyword action moves the target creature to the graveyard."""
    game = fresh_game()
    doomed = place_on_battlefield(make_creature('Doomed', 2, 2), 1, game.zones)
    oracle = 'Destroy target creature.'
    assert has_registered_keyword(oracle, 'Destroy')
    game.zones.leave_battlefield(doomed, Zone.GRAVEYARD, 'destroy', game)
    assert game.zones.find_permanent(doomed.obj_id) is None
    assert len(game.zones.player_zones[1].graveyard) == 1


def test_play_puts_top_land_on_battlefield():
    """Play puts the top land from your library onto the battlefield."""
    game = fresh_game()
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_land('Forest', 'G')),
    )
    assert has_play('Play.')
    detail = play_top_card(game.zones, 0)
    assert 'played Forest' in detail
    forests = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == 0 and 'Forest' in perm.type_line
    ]
    assert len(forests) == 1


def test_abandon_discards_two_hand_cards():
    """Abandon discards two cards from hand."""
    game = fresh_game()
    add_to_hand(make_instant('One'), 0, game.zones)
    add_to_hand(make_instant('Two'), 0, game.zones)
    add_to_hand(make_instant('Three'), 0, game.zones)
    assert has_abandon('Abandon.')
    detail = abandon_hand(game.zones, 0)
    assert 'abandoned 2' in detail
    assert len(game.zones.player_zones[0].hand) == 1
    assert len(game.zones.player_zones[0].graveyard) == 2


def test_assemble_creates_knight_token():
    """Assemble creates a 2/2 Knight creature token."""
    game = fresh_game()
    assert has_assemble('Assemble.')
    detail = assemble_legion(game.zones, 0)
    assert 'assembled' in detail
    knights = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == 0 and 'Knight' in perm.type_line
    ]
    assert len(knights) == 1


def test_reveal_logs_top_library_card():
    """Reveal logs the top card of the library."""
    game = fresh_game()
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Secret')),
    )
    assert has_reveal('Reveal.')
    detail = reveal_top_card(game.zones, 0)
    assert 'revealed Secret' in detail


def test_double_deals_damage_twice_to_opponent():
    """Double deals twice the parsed damage to an opponent."""
    game = fresh_game()
    start_life = game.players[1].life
    oracle = 'Double — Deal 3 damage to any target.'
    assert has_double(oracle)
    detail = apply_double_damage(game, 0, oracle)
    assert detail is not None
    assert 'double dealt 6' in detail
    assert game.players[1].life == start_life - 6
