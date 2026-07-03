"""Unit tests for keyword actions batch 6.

Vote, Transform, Cloak, Conjure, Role token, and Regenerate.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.specialty import (
    cloak_creature,
    conjure_to_hand,
    create_role_token,
    has_cloak,
    has_conjure,
    has_role_token,
    has_transform,
    has_vote,
    resolve_vote,
    transform_creature,
)
from engine.abilities.keywords.handlers import grant_regeneration_shield
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_vote_resolves_with_controller_winning():
    """Vote logs a simplified council outcome."""
    oracle = 'Each player votes. Vote for more creatures.'
    assert has_vote(oracle)
    detail = resolve_vote(oracle)
    assert 'vote resolved' in detail


def test_transform_toggles_creature_face_state():
    """Transform toggles a creature between face-up and face-down."""
    game = fresh_game()
    werewolf = place_on_battlefield(make_creature('Wolf', 3, 3), 0, game.zones)
    assert has_transform('Transform.')
    assert not werewolf.face_down
    detail = transform_creature(game.zones, str(werewolf.obj_id))
    assert detail is not None
    assert werewolf.face_down
    transform_creature(game.zones, str(werewolf.obj_id))
    assert not werewolf.face_down


def test_cloak_turns_creature_face_down():
    """Cloak turns the target creature face down."""
    game = fresh_game()
    spy = place_on_battlefield(make_creature('Spy', 2, 2), 0, game.zones)
    assert has_cloak('Cloak target creature.')
    detail = cloak_creature(game.zones, str(spy.obj_id))
    assert detail is not None
    assert spy.face_down


def test_conjure_puts_library_card_into_hand():
    """Conjure adds a card from the library to hand."""
    game = fresh_game()
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Conjured')),
    )
    oracle = 'Conjure a card named Conjured into your hand.'
    assert has_conjure(oracle)
    detail = conjure_to_hand(game.zones, 0, oracle)
    assert 'conjured Conjured' in detail
    assert len(game.zones.player_zones[0].hand) == 1


def test_role_token_creates_parsed_creature_token():
    """Role token creates a creature token from oracle text."""
    game = fresh_game()
    oracle = 'Create a 1/1 white Soldier creature token.'
    assert has_role_token('Role token — ' + oracle)
    detail = create_role_token(game.zones, 0, oracle)
    assert detail is not None
    assert 'created' in detail
    soldiers = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == 0 and 'Soldier' in perm.type_line
    ]
    assert len(soldiers) == 1


def test_regenerate_grants_regeneration_shield():
    """Regenerate marks a creature with a regeneration shield."""
    game = fresh_game()
    troll = place_on_battlefield(make_creature('Troll', 4, 4), 0, game.zones)
    oracle = 'Regenerate target creature.'
    assert has_registered_keyword(oracle, 'Regenerate')
    grant_regeneration_shield(troll)
    assert troll.counters.get('regeneration shield') == 1
