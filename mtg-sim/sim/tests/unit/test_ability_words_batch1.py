"""Unit tests for ability words batch 1: Enrage, Domain, Addendum, Parley, Kinship, Threshold."""

from __future__ import annotations

from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.ability_words.detect import has_ability_word_card
from engine.abilities.keywords.ability_words.effects import KinshipEffect, ParleyEffect
from engine.abilities.keywords.ability_words.register import wired_ability_word_names
from engine.core.game_object import CardObject
from engine.core.turn_structure import Step
from tests.ability_word_test_helpers import (
    fire_test_instant_cast,
    fresh_game_with_spell_cast_host,
    top_trigger,
)
from tests.conftest import fresh_game, make_card, make_creature, make_instant, place_on_battlefield


def test_enrage_triggers_when_creature_is_damaged():
    """Enrage registers a combat-damage trigger on the damaged creature."""
    game = fresh_game()
    raptor = place_on_battlefield(
        make_creature('Raptor', 2, 2, oracle='Enrage — Draw a card.'),
        0,
        game.zones,
    )
    assert raptor.card_info is not None
    assert has_ability_word_card(raptor.card_info, 'Enrage')
    register_permanent_ability_words(raptor, game.trigger_registry)
    piker = place_on_battlefield(make_creature('Piker', 1, 1), 1, game.zones)
    game.fire_combat_damage_triggers(piker, 1, damaged_permanent=raptor)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == raptor.obj_id


def test_domain_triggers_with_basic_land_types():
    """Domain fires when you cast a spell while controlling basic lands."""
    game, source = fresh_game_with_spell_cast_host(
        'Domain — Draw a card.',
        name='Scout',
    )
    place_on_battlefield(
        make_card(name='Forest', type_line='Basic Land — Forest'),
        0,
        game.zones,
    )
    place_on_battlefield(
        make_card(name='Island', type_line='Basic Land — Island'),
        0,
        game.zones,
    )
    fire_test_instant_cast(game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_addendum_triggers_during_main_phase():
    """Addendum fires when you cast during your main phase."""
    game, source = fresh_game_with_spell_cast_host(
        'Addendum — Draw a card.',
        name='Legionnaire',
    )
    game.turn.context.step = Step.PRECOMBAT_MAIN
    fire_test_instant_cast(game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_parley_triggers_at_beginning_of_combat():
    """Parley registers a beginning-of-combat trigger with ParleyEffect."""
    game = fresh_game()
    captain = place_on_battlefield(
        make_creature('Captain', 2, 2, oracle='Parley — Draw a card.'),
        0,
        game.zones,
    )
    assert 'Parley' in wired_ability_word_names(captain.oracle_text)
    register_permanent_ability_words(captain, game.trigger_registry)
    game.fire_step_triggers(Step.BEGIN_COMBAT)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == captain.obj_id
    assert isinstance(trigger.effect, ParleyEffect)


def test_kinship_triggers_at_beginning_of_upkeep():
    """Kinship registers an upkeep trigger with KinshipEffect."""
    game = fresh_game()
    elder = place_on_battlefield(
        make_creature('Elder', 2, 2, oracle='Kinship — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(elder, game.trigger_registry)
    game.fire_step_triggers(Step.UPKEEP)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == elder.obj_id
    assert isinstance(trigger.effect, KinshipEffect)


def test_threshold_triggers_with_seven_cards_in_graveyard():
    """Threshold fires when you cast with seven or more cards in graveyard."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature('Anurid', 2, 2, oracle='Threshold — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    for idx in range(7):
        game.zones.player_zones[0].graveyard.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_instant(f'Spell {idx}'),
            ),
        )
    fire_test_instant_cast(game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id
