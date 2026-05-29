"""Unit and game-loop tests for disguise and embalm (batch 17)."""

from __future__ import annotations

from engine.abilities.keywords.casting.embalm import (
    can_embalm,
    create_embalm_token_in_exile,
    embalm_mana_needed,
    has_embalm,
)
from engine.abilities.keywords.other.disguise import (
    apply_turn_up_disguise,
    disguise_face_down_mana_needed,
    has_disguise,
    normalize_disguise_cast,
)
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from engine.game import create_game
from engine.game.helpers import card_to_client, HandCastContext
from tests.conftest import (
    cast_announce_options,
    fresh_game,
    make_creature,
    make_deck,
    make_land,
    place_on_battlefield,
)


def test_has_disguise_and_face_down_cost():
    """Disguise uses a fixed face-down mana cost."""
    card = make_creature('Agent', 4, 4, oracle='Disguise {2}{U}')
    assert has_disguise(card)
    assert normalize_disguise_cast(card, True)
    assert disguise_face_down_mana_needed() == (3, 0)


def test_turn_up_disguise_reveals_creature():
    """Turning face up removes the face-down status."""
    game = fresh_game()
    card = make_creature('Agent', 4, 4, oracle='Disguise {2}{U}')
    perm = place_on_battlefield(card, 0, game.zones)
    perm.face_down = True
    detail = apply_turn_up_disguise(perm)
    assert detail
    assert not perm.face_down


def test_embalm_parses_cost_and_creates_token():
    """Embalm cost parses and creates a token in exile."""
    honored = make_creature('Honored', 4, 4, oracle='Embalm {3}{W}')
    assert has_embalm(honored)
    assert embalm_mana_needed(honored)[0] == 4
    game = fresh_game()
    detail = create_embalm_token_in_exile(game.zones, 0, honored)
    assert 'embalmed' in detail
    assert len(game.zones.player_zones[0].exile) == 1


def test_can_embalm_main_phase_only():
    """Embalm may only be activated on an empty stack main phase."""
    card = make_creature('Honored', 4, 4, oracle='Embalm {1}{W}')
    assert can_embalm(card, 'main1', True)
    assert not can_embalm(card, 'attack', False)


def test_card_to_client_disguise_and_embalm_flags():
    """Hand cards expose disguise and embalm for the play UI."""
    ctx = HandCastContext(controller_idx=0)
    disguised = card_to_client(
        0,
        make_creature('Shade', 3, 3, oracle='Disguise {1}{B}'),
        10,
        ctx,
    )
    embalmed = card_to_client(
        0,
        make_creature('Honored', 4, 4, oracle='Embalm {2}{W}'),
        10,
        ctx,
    )
    assert disguised['hasDisguise'] is True
    assert embalmed['hasEmbalm'] is True


def test_game_cast_disguise_face_down():
    """Casting for disguise enters as a face-down creature."""
    agent = make_creature(
        name='Agent',
        cmc=4,
        oracle='Disguise {2}{U}',
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    for _ in range(3):
        land = CardObject(controller_idx=0, owner_idx=0, card_info=make_land())
        game.state.zones.enter_battlefield(land, 0, 'test_setup', Zone.HAND)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=agent),
    ]
    data = game.action_cast(
        0,
        cast_options=cast_announce_options(cast_for_disguise=True),
    )
    assert 'error' not in data
    perm = next(p for p in game.state.zones.battlefield if p.name == 'Agent')
    assert perm.face_down


def test_game_embalm_from_hand():
    """Embalm exiles the card from hand and creates a token in exile."""
    honored = make_creature(
        name='Honored',
        cmc=4,
        oracle='Embalm {2}{W}',
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    for _ in range(3):
        land = CardObject(controller_idx=0, owner_idx=0, card_info=make_land())
        game.state.zones.enter_battlefield(land, 0, 'test_setup', Zone.HAND)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=honored),
    ]
    data = game.action_embalm(0)
    assert 'error' not in data
    assert len(game.state.zones.player_zones[0].hand) == 0
    assert len(game.state.zones.player_zones[0].exile) == 2
