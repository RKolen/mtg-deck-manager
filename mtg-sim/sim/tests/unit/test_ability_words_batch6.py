"""Unit tests for ability words batch 6.

Void, Disappear, Infusion, Landship, Opus, and Spell mastery.
"""

from __future__ import annotations

from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.ability_words.effects import AbilityWordEffect
from engine.core.game_object import CardObject
from tests.ability_word_test_helpers import top_trigger
from tests.conftest import (
    fresh_game,
    make_artifact,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_void_triggers_when_opponent_has_empty_hand():
    """Void fires when an opponent has no cards in hand."""
    game = fresh_game()
    voidmage = place_on_battlefield(
        make_creature('Voidmage', 2, 2, oracle='Void — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(voidmage, game.trigger_registry)
    game.zones.player_zones[1].hand.clear()
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Drain')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == voidmage.obj_id


def test_disappear_triggers_after_opponent_was_damaged():
    """Disappear fires after an opponent was dealt damage this turn."""
    game = fresh_game()
    stalker = place_on_battlefield(
        make_creature('Stalker', 1, 1, oracle='Disappear — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(stalker, game.trigger_registry)
    game.players[1].was_dealt_damage_this_turn = True
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Fade')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == stalker.obj_id


def test_infusion_triggers_with_artifact_present():
    """Infusion fires when you control an artifact."""
    game = fresh_game()
    artificer = place_on_battlefield(
        make_creature('Artificer', 2, 2, oracle='Infusion — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(artificer, game.trigger_registry)
    place_on_battlefield(make_artifact('Lens'), 0, game.zones)
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Charge')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == artificer.obj_id


def test_landship_triggers_with_island_on_battlefield():
    """Landship fires when you control an Island."""
    game = fresh_game()
    sailor = place_on_battlefield(
        make_creature('Sailor', 2, 2, oracle='Landship — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(sailor, game.trigger_registry)
    place_on_battlefield(
        make_card(name='Island', type_line='Basic Land — Island'),
        0,
        game.zones,
    )
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Tide')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == sailor.obj_id


def test_opus_triggers_with_full_hand():
    """Opus fires when you have five or more cards in hand."""
    game = fresh_game()
    composer = place_on_battlefield(
        make_creature('Composer', 3, 3, oracle='Opus — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(composer, game.trigger_registry)
    for idx in range(5):
        game.zones.player_zones[0].hand.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_instant(f'Note {idx}'),
            ),
        )
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Finale')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == composer.obj_id


def test_spell_mastery_triggers_on_instant_cast():
    """Spell mastery fires when you cast an instant or sorcery."""
    game = fresh_game()
    scholar = place_on_battlefield(
        make_creature('Scholar', 1, 1, oracle='Spell mastery — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(scholar, game.trigger_registry)
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Lesson')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == scholar.obj_id
    assert isinstance(trigger.effect, AbilityWordEffect)
