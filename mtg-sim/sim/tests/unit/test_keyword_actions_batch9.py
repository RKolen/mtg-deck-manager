"""Unit tests for keyword actions batch 9.

Set in motion, Cast, Meld, Exchange, Planeswalk, and Roll to Visit Your Attractions.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.specialty import (
    cast_from_library,
    exchange_library_tops,
    has_cast_action,
    has_exchange,
    has_meld,
    has_planeswalk,
    has_roll_attractions,
    has_set_in_motion,
    meld_permanents,
    planeswalk_creature,
    roll_attractions,
    set_in_motion,
)
from engine.core.game_object import CardObject
from tests.conftest import (
    _CardStats,
    add_to_library,
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_set_in_motion_adds_time_counter():
    """Set in motion puts a time counter on the target permanent."""
    game = fresh_game()
    clock = place_on_battlefield(make_creature('Clock', 0, 4), 0, game.zones)
    assert has_set_in_motion('Set in motion.')
    detail = set_in_motion(game.zones, str(clock.obj_id))
    assert detail is not None
    assert clock.counters.get('time') == 1


def test_cast_manifests_top_library_card():
    """Cast manifests the top card of your library face down."""
    game = fresh_game()
    add_to_library(make_creature('Mystery', 3, 3), 0, game.zones)
    assert has_cast_action('Cast.')
    detail = cast_from_library(game.zones, 0)
    assert 'cast Mystery' in detail
    assert len(game.zones.battlefield) == 1


def test_meld_logs_two_target_permanents():
    """Meld logs melding two permanents together."""
    game = fresh_game()
    top = place_on_battlefield(make_creature('Top', 3, 3), 0, game.zones)
    bottom = place_on_battlefield(make_creature('Bottom', 4, 4), 0, game.zones)
    assert has_meld('Meld.')
    detail = meld_permanents(game.zones, str(top.obj_id), str(bottom.obj_id))
    assert detail is not None
    assert 'melded Top with Bottom' in detail


def test_exchange_swaps_library_tops_between_players():
    """Exchange swaps the top card of each player's library."""
    game = fresh_game()
    ours = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_instant('Ours', cmc=1.0),
    )
    theirs = CardObject(
        controller_idx=1,
        owner_idx=1,
        card_info=make_instant('Theirs', cmc=2.0),
    )
    game.zones.player_zones[0].library.append(ours)
    game.zones.player_zones[1].library.append(theirs)
    assert has_exchange('Exchange.')
    detail = exchange_library_tops(game.zones, 0)
    assert detail == 'exchanged top of libraries'
    assert game.zones.player_zones[0].library[0] is theirs
    assert game.zones.player_zones[1].library[0] is ours


def test_planeswalk_adds_loyalty_to_planeswalker():
    """Planeswalk adds a loyalty counter to a planeswalker permanent."""
    game = fresh_game()
    walker = place_on_battlefield(
        make_card(
            'Jace',
            type_line='Legendary Planeswalker — Jace',
            stats=_CardStats(cmc=4.0, pt='0/0'),
        ),
        0,
        game.zones,
    )
    assert has_planeswalk('Planeswalk.')
    detail = planeswalk_creature(game.zones, str(walker.obj_id))
    assert detail is not None
    assert walker.counters.get('loyalty') == 1


def test_roll_attractions_advances_visit_counter():
    """Roll to Visit Your Attractions advances the attractions counter."""
    game = fresh_game()
    assert has_roll_attractions('Roll to Visit Your Attractions.')
    detail = roll_attractions(game, 0)
    assert 'rolled attractions' in detail
    assert game.players[0].attractions == 1
