"""Unit tests for ability words batch 2: Formidable, Undergrowth, Flurry, and more."""

from __future__ import annotations

from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.ability_words.detect import has_ability_word_card
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from tests.ability_word_test_helpers import (
    fire_test_instant_cast,
    fresh_game_with_spell_cast_host,
    top_trigger,
)
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_card,
    make_creature,
    place_on_battlefield,
)


def test_formidable_triggers_with_power_eight_creature():
    """Formidable fires when you control a creature with power 8 or greater."""
    game, source = fresh_game_with_spell_cast_host(
        'Formidable — Draw a card.',
        name='Channeler',
    )
    place_on_battlefield(make_creature('Titan', 8, 8), 0, game.zones)
    assert source.card_info is not None
    assert has_ability_word_card(source.card_info, 'Formidable')
    fire_test_instant_cast(game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_undergrowth_triggers_with_creature_in_graveyard():
    """Undergrowth fires when your graveyard contains a creature card."""
    game, source = fresh_game_with_spell_cast_host(
        'Undergrowth — Draw a card.',
        name='Golgari',
    )
    game.zones.player_zones[0].graveyard.append(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_creature('Corpse', 2, 2),
        ),
    )
    fire_test_instant_cast(game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_flurry_triggers_on_second_spell_cast():
    """Flurry fires when you cast your second spell this turn."""
    game, source = fresh_game_with_spell_cast_host(
        'Flurry — Draw a card.',
        name='Monk',
    )
    game.players[0].spells_cast_this_turn = 2
    fire_test_instant_cast(game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_celebration_triggers_after_two_permanents_entered():
    """Celebration fires after two or more permanents entered this turn."""
    game, source = fresh_game_with_spell_cast_host(
        'Celebration — Draw a card.',
        name='Reveler',
    )
    game.players[0].permanents_entered_this_turn = 2
    fire_test_instant_cast(game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_pack_tactics_triggers_with_larger_ally_attacking():
    """Pack tactics fires when this creature attacks alongside a bigger ally."""
    game = fresh_game()
    scout = place_on_battlefield(
        make_creature('Scout', 2, 2, oracle='Pack tactics — Draw a card.'),
        0,
        game.zones,
        sick=False,
    )
    place_on_battlefield(make_creature('Brute', 5, 5), 0, game.zones)
    register_permanent_ability_words(scout, game.trigger_registry)
    game.fire_attack_triggers(scout)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == scout.obj_id


def test_alliance_triggers_when_ally_enters():
    """Alliance fires when another Ally enters under your control."""
    game = fresh_game()
    leader = place_on_battlefield(
        make_creature('Leader', 2, 2, oracle='Alliance — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(leader, game.trigger_registry)
    ally = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_card(
            name='Friend',
            type_line='Creature — Human Ally',
            stats=_CardStats(pt='2/2'),
        ),
    )
    game.zones.enter_battlefield(ally, 0, 'test', Zone.HAND)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == leader.obj_id
