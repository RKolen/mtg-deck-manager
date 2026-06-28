"""Unit tests for ability words batch 7.

Join forces, Fathomless descent, Tempting offer, Hero's Reward, Cohort,
and council-style voting words.
"""

from __future__ import annotations

from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.ability_words.detect import has_ability_word_card
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from tests.ability_word_test_helpers import (
    assert_spell_cast_triggers_host,
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

_COUNCIL_WORDS = (
    'Secret council',
    'Will of the council',
    "Council's dilemma",
)


def test_join_forces_triggers_with_two_creatures_on_battlefield():
    """Join forces fires when you cast a spell while controlling two creatures."""
    game, captain = fresh_game_with_spell_cast_host(
        'Join forces — Draw a card.',
        name='Captain',
    )
    place_on_battlefield(make_creature('Mate', 2, 2), 0, game.zones)
    assert_spell_cast_triggers_host(game, captain)


def test_fathomless_descent_triggers_with_ten_graveyard_cards():
    """Fathomless descent fires with ten or more cards in your graveyard."""
    game = fresh_game()
    diver = place_on_battlefield(
        make_creature('Diver', 2, 2, oracle='Fathomless descent — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(diver, game.trigger_registry)
    graveyard = game.zones.player_zones[0].graveyard
    for idx in range(10):
        graveyard.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_instant(f'Scrap {idx}'),
            ),
        )
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Plunge')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == diver.obj_id


def test_tempting_offer_triggers_on_high_cmc_spell():
    """Tempting offer fires when you cast a spell with mana value six or greater."""
    game = fresh_game()
    tempter = place_on_battlefield(
        make_creature('Tempter', 3, 3, oracle='Tempting offer — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(tempter, game.trigger_registry)
    costly = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_instant('Temptation', cmc=6.0),
    )
    game.fire_spell_cast_triggers(costly)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == tempter.obj_id


def test_heros_reward_triggers_after_creature_death():
    """Hero's Reward fires when you cast a spell after a creature died this turn."""
    game = fresh_game()
    game.creature_died_this_turn = True
    champion = place_on_battlefield(
        make_creature('Champion', 2, 2, oracle="Hero's Reward — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(champion, game.trigger_registry)
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Rally')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == champion.obj_id


def test_cohort_triggers_when_ally_creature_enters():
    """Cohort fires when another Ally enters under your control."""
    game = fresh_game()
    warlord = place_on_battlefield(
        make_creature('Warlord', 2, 2, oracle='Cohort — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(warlord, game.trigger_registry)
    assert warlord.card_info is not None
    assert has_ability_word_card(warlord.card_info, 'Cohort')
    recruit = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_card(
            name='Recruit',
            type_line='Creature — Kor Ally',
            stats=_CardStats(pt='1/1'),
        ),
    )
    game.zones.enter_battlefield(recruit, 0, 'test', Zone.HAND)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == warlord.obj_id


def test_council_ability_words_trigger_on_spell_cast():
    """Secret council, Will of the council, and Council's dilemma fire on cast."""
    for word in _COUNCIL_WORDS:
        game = fresh_game()
        oracle = f'{word} — Draw a card.'
        senator = place_on_battlefield(
            make_creature('Senator', 1, 1, oracle=oracle),
            0,
            game.zones,
        )
        register_permanent_ability_words(senator, game.trigger_registry)
        assert senator.card_info is not None
        assert has_ability_word_card(senator.card_info, word)
        game.fire_spell_cast_triggers(
            CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Vote')),
        )
        trigger = top_trigger(game)
        assert trigger.source_permanent_id == senator.obj_id
