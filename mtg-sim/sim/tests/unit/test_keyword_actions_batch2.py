"""Unit tests for keyword actions batch 2.

Explore, Connive, Populate, Adapt, Learn, and Create.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.resolve import (
    ActionContext,
    resolve_spell_keyword_actions,
)
from engine.abilities.keywords.actions.specialty import adapt_creature, has_adapt, has_learn
from engine.abilities.keywords.actions.tokens import (
    connive,
    create_creature_token_from_oracle,
    explore_creature,
    has_connive,
    has_create,
    has_explore,
    has_populate,
    investigate,
    populate_token,
)
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_explore_puts_counter_on_creature():
    """Explore adds a +1/+1 counter to the exploring creature."""
    game = fresh_game()
    scout = place_on_battlefield(make_creature('Scout', 1, 1), 0, game.zones)
    assert has_explore('Whenever this creature explores, draw a card.')
    name = explore_creature(scout)
    assert name == scout.name
    assert scout.counters.get('+1/+1') == 1


def test_connive_draws_then_mills_library():
    """Connive draws a card and mills cards from the library."""
    game = fresh_game()
    top = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Top'))
    bottom = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Bottom'))
    game.zones.player_zones[0].library.extend([bottom, top])
    assert has_connive('Connive 2.')
    detail = connive(
        game.zones,
        0,
        'Connive 2.',
        lambda player_idx, count: [
            card for _ in range(count)
            if (card := game.zones.draw(player_idx)) is not None
        ],
    )
    assert 'connived' in detail
    assert len(game.zones.player_zones[0].hand) == 1
    assert len(game.zones.player_zones[0].graveyard) == 2


def test_populate_copies_largest_token():
    """Populate copies the largest token you control."""
    game = fresh_game()
    assert has_populate('Populate.')
    investigate(game.zones, 0, 1)
    name = populate_token(game.zones, 0)
    assert name is not None
    clues = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == 0 and 'Clue' in perm.type_line
    ]
    assert len(clues) == 2


def test_adapt_puts_counters_once_per_creature():
    """Adapt places +1/+1 counters the first time only."""
    game = fresh_game()
    hydra = place_on_battlefield(make_creature('Hydra', 0, 0), 0, game.zones)
    oracle = 'Adapt 2.'
    assert has_adapt(oracle)
    detail = adapt_creature(game.zones, str(hydra.obj_id), oracle)
    assert detail is not None
    assert hydra.counters.get('+1/+1') == 2
    assert adapt_creature(game.zones, str(hydra.obj_id), oracle) is None


def test_learn_draws_a_card():
    """Learn draws a card from the library."""
    game = fresh_game()
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Lesson')),
    )
    assert has_learn('Learn.')
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Learn',
    ))
    assert detail is not None
    assert 'learned' in detail
    assert len(game.zones.player_zones[0].hand) == 1


def test_create_makes_creature_token_from_oracle():
    """Create spawns a creature token parsed from oracle text."""
    game = fresh_game()
    oracle = 'Create a 1/1 white Soldier creature token.'
    assert has_create(oracle)
    token_name = create_creature_token_from_oracle(game.zones, 0, oracle)
    assert token_name is not None
    assert 'Soldier' in token_name
    soldiers = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == 0 and 'Soldier' in perm.type_line
    ]
    assert len(soldiers) == 1
