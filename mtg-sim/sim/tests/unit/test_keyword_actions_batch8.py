"""Unit tests for keyword actions batch 8.

Open an Attraction, Time Travel, Exile, Endure, Manifest dread, and Prepared.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.library import manifest_top_of_library
from engine.abilities.keywords.actions.specialty import (
    endure_creature,
    has_endure,
    has_open_attraction,
    has_prepared,
    has_time_travel,
    open_attraction,
    prepared_creature,
    time_travel,
)
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_open_attraction_increments_attractions_counter():
    """Open an Attraction advances the player's attractions count."""
    game = fresh_game()
    assert has_open_attraction('Open an Attraction.')
    assert game.players[0].attractions == 0
    detail = open_attraction(game, 0)
    assert 'opened Attraction #1' in detail
    assert game.players[0].attractions == 1


def test_time_travel_adds_lore_counter():
    """Time Travel puts a lore counter on the target permanent."""
    game = fresh_game()
    sage = place_on_battlefield(make_creature('Sage', 2, 3), 0, game.zones)
    assert has_time_travel('Time Travel.')
    detail = time_travel(game.zones, str(sage.obj_id))
    assert detail is not None
    assert sage.counters.get('lore') == 1


def test_exile_action_moves_creature_to_exile_zone():
    """Exile keyword action moves the target creature to exile."""
    game = fresh_game()
    banished = place_on_battlefield(make_creature('Banished', 2, 2), 1, game.zones)
    oracle = 'Exile target creature.'
    assert has_registered_keyword(oracle, 'Exile')
    game.zones.leave_battlefield(banished, Zone.EXILE, 'exile', game)
    assert game.zones.find_permanent(banished.obj_id) is None
    assert len(game.zones.player_zones[1].exile) == 1


def test_endure_marks_creature_with_endure_counter():
    """Endure marks a creature with an endure counter."""
    game = fresh_game()
    survivor = place_on_battlefield(make_creature('Survivor', 3, 3), 0, game.zones)
    assert has_endure('Endure.')
    detail = endure_creature(game.zones, str(survivor.obj_id))
    assert detail is not None
    assert survivor.counters.get('endure') == 1


def test_manifest_dread_puts_library_card_face_down():
    """Manifest dread manifests the top library card face down."""
    game = fresh_game()
    game.zones.player_zones[0].library.append(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_creature('Hidden', 4, 4),
        ),
    )
    assert has_registered_keyword('Manifest dread.', 'Manifest dread')
    perm = manifest_top_of_library(game.zones, 0, cause='manifest dread')
    assert perm is not None
    assert perm.face_down


def test_prepared_marks_creature_as_prepared():
    """Prepared marks a creature with the prepared counter."""
    game = fresh_game()
    scout = place_on_battlefield(make_creature('Scout', 2, 1), 0, game.zones)
    assert has_prepared('Prepared.')
    detail = prepared_creature(game.zones, str(scout.obj_id))
    assert detail is not None
    assert scout.counters.get('prepared') == 1
