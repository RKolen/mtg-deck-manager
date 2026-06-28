"""Unit tests for ability words batch 4: Adamant, Eerie, Eminence, Grandeur, Heroic, Kinfall."""

from __future__ import annotations

from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.ability_words.create_token_effect import CreateTokenEffect
from engine.core.game_object import CardObject, Target
from engine.core.turn_structure import Step
from engine.core.zones import Zone
from tests.ability_word_test_helpers import (
    fresh_game_with_spell_cast_host,
    top_trigger,
)
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_adamant_triggers_during_postcombat_main():
    """Adamant fires when you cast during your main phase."""
    game = fresh_game()
    legionnaire = place_on_battlefield(
        make_creature('Legionnaire', 2, 2, oracle='Adamant — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(legionnaire, game.trigger_registry)
    game.turn.context.step = Step.POSTCOMBAT_MAIN
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Order')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == legionnaire.obj_id


def test_eerie_triggers_while_enchantment_is_controlled():
    """Eerie fires when you cast while controlling an enchantment."""
    game = fresh_game()
    place_on_battlefield(
        make_card(name='Shrine', type_line='Enchantment'),
        0,
        game.zones,
    )
    mystic = place_on_battlefield(
        make_creature('Mystic', 1, 1, oracle='Eerie — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(mystic, game.trigger_registry)
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Glimpse')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == mystic.obj_id


def test_eminence_triggers_on_any_spell_cast():
    """Eminence fires whenever you cast a spell while this is on the battlefield."""
    game, commander = fresh_game_with_spell_cast_host(
        'Eminence — Draw a card.',
        name='Commander',
    )
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Sign')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == commander.obj_id


def test_grandeur_triggers_at_upkeep_with_legendary_in_hand():
    """Grandeur fires at upkeep when you have a legendary card in hand."""
    game = fresh_game()
    noble = place_on_battlefield(
        make_creature('Noble', 4, 4, oracle='Grandeur — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(noble, game.trigger_registry)
    game.zones.player_zones[0].hand.append(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_card(
                name='Legend',
                type_line='Legendary Creature — Elf Druid',
                stats=_CardStats(pt='2/2'),
            ),
        ),
    )
    game.fire_step_triggers(Step.UPKEEP)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == noble.obj_id


def test_heroic_triggers_when_spell_targets_source():
    """Heroic fires when you cast a spell targeting this permanent."""
    game = fresh_game()
    crusader = place_on_battlefield(
        make_creature(
            'Crusader',
            1,
            1,
            oracle=(
                'Heroic — Whenever you cast a spell that targets Crusader, '
                'create a 1/1 red Soldier creature token.'
            ),
        ),
        0,
        game.zones,
    )
    register_permanent_ability_words(crusader, game.trigger_registry)
    growth = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_instant('Strength', oracle='Target creature gets +3/+1.'),
    )
    game.fire_spell_cast_triggers(
        growth,
        (Target(obj_id=crusader.obj_id),),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == crusader.obj_id
    assert isinstance(trigger.effect, CreateTokenEffect)


def test_kinfall_triggers_when_large_creature_enters():
    """Kinfall fires when a creature with power 4 or greater enters."""
    game = fresh_game()
    kinhost = place_on_battlefield(
        make_creature('Kinhost', 1, 1, oracle='Kinfall — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(kinhost, game.trigger_registry)
    giant = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature('Giant', 5, 5),
    )
    game.zones.enter_battlefield(giant, 0, 'test', Zone.HAND)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == kinhost.obj_id
