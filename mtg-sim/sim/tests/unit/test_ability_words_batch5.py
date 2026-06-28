"""Unit tests for ability words batch 5.

Legacy, Paradox, Radiance, Teamwork, Vivid, and Start your engines.
"""

from __future__ import annotations

from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.core.game_object import CardObject
from tests.ability_word_test_helpers import top_trigger
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_legacy_triggers_with_legendary_card_in_graveyard():
    """Legacy fires when you cast with a legendary card in your graveyard."""
    game = fresh_game()
    historian = place_on_battlefield(
        make_creature('Historian', 2, 2, oracle='Legacy — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(historian, game.trigger_registry)
    game.zones.player_zones[0].graveyard.append(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_card(
                name='Champion',
                type_line='Legendary Creature — Human',
                stats=_CardStats(pt='3/3'),
            ),
        ),
    )
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Chronicle')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == historian.obj_id


def test_paradox_triggers_on_high_mana_value_spell():
    """Paradox fires when you cast a spell with mana value 7 or greater."""
    game = fresh_game()
    sage = place_on_battlefield(
        make_creature('Sage', 1, 1, oracle='Paradox — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(sage, game.trigger_registry)
    game.fire_spell_cast_triggers(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_instant('Titanic', cmc=7, mana_cost='{5}{U}{U}'),
        ),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == sage.obj_id


def test_radiance_triggers_with_white_permanent():
    """Radiance fires when you control a white permanent."""
    game = fresh_game()
    cleric = place_on_battlefield(
        make_creature('Cleric', 2, 2, oracle='Radiance — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(cleric, game.trigger_registry)
    place_on_battlefield(
        make_card(name='Plains', type_line='Basic Land — Plains'),
        0,
        game.zones,
    )
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Prayer')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == cleric.obj_id


def test_teamwork_triggers_with_two_creatures():
    """Teamwork fires when you control two or more creatures."""
    game = fresh_game()
    captain = place_on_battlefield(
        make_creature('Captain', 2, 2, oracle='Teamwork — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(captain, game.trigger_registry)
    place_on_battlefield(make_creature('Ally', 1, 1), 0, game.zones)
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Rally')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == captain.obj_id


def test_vivid_triggers_with_charge_counter_land():
    """Vivid fires when you control a land with a charge counter."""
    game = fresh_game()
    mage = place_on_battlefield(
        make_creature('Mage', 1, 1, oracle='Vivid — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(mage, game.trigger_registry)
    meadow = place_on_battlefield(
        make_card(name='Vivid Meadow', type_line='Land'),
        0,
        game.zones,
    )
    meadow.counters['charge'] = 1
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Surge')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == mage.obj_id


def test_start_your_engines_triggers_on_turn_four():
    """Start your engines! fires when you cast on turn four or later."""
    game = fresh_game()
    racer = place_on_battlefield(
        make_creature('Racer', 3, 3, oracle='Start your engines! — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(racer, game.trigger_registry)
    game.turn.context.turn_number = 4
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Boost')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == racer.obj_id
