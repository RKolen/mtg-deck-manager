"""Unit tests for ability words batch 3: Converge, Lieutenant, Chroma, Renew, Valiant, Corrupted."""

from __future__ import annotations

from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.ability_words.effects import ValiantEffect
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from tests.ability_word_test_helpers import (
    assert_source_etb_trigger,
    fire_test_instant_cast,
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


def test_converge_triggers_with_colored_permanents():
    """Converge fires when you control permanents with colored mana costs."""
    game = fresh_game()
    host = place_on_battlefield(
        make_creature('Converger', 1, 1, oracle='Converge — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(host, game.trigger_registry)
    place_on_battlefield(
        make_creature('Shaman', 2, 2, mana_cost='{R}{G}'),
        0,
        game.zones,
    )
    game.fire_spell_cast_triggers(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Bolt')),
    )
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == host.obj_id


def test_lieutenant_triggers_with_legendary_creature_present():
    """Lieutenant fires on ETB when you control a legendary creature."""
    game = fresh_game()
    place_on_battlefield(
        make_card(
            name='Captain',
            type_line='Legendary Creature — Human Soldier',
            stats=_CardStats(pt='3/3'),
        ),
        0,
        game.zones,
    )
    lieutenant_card = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature('Lieutenant', 2, 2, oracle='Lieutenant — Draw a card.'),
    )
    lieutenant = game.zones.enter_battlefield(lieutenant_card, 0, 'test', Zone.HAND)
    register_permanent_ability_words(lieutenant, game.trigger_registry)
    assert_source_etb_trigger(game, lieutenant)


def test_chroma_triggers_on_multicolor_spell_cast():
    """Chroma fires when you cast a spell with colored mana in its cost."""
    game, source = fresh_game_with_spell_cast_host(
        'Chroma — Draw a card.',
        name='Pyromancer',
    )
    spell = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_instant('Charm', mana_cost='{U}{R}'),
    )
    game.fire_spell_cast_triggers(spell)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_renew_triggers_when_creature_leaves():
    """Renew fires when another creature you control leaves the battlefield."""
    game = fresh_game()
    renewer = place_on_battlefield(
        make_creature('Renewer', 2, 2, oracle='Renew — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_ability_words(renewer, game.trigger_registry)
    ally = place_on_battlefield(make_creature('Ally', 1, 1), 0, game.zones)
    game.zones.leave_battlefield(ally, Zone.GRAVEYARD, 'destroy', game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == renewer.obj_id


def test_valiant_triggers_on_first_attack():
    """Valiant registers a first-attack trigger with ValiantEffect."""
    game = fresh_game()
    scout = place_on_battlefield(
        make_creature('Scout', 2, 2, oracle='Valiant — Draw a card.'),
        0,
        game.zones,
        sick=False,
    )
    register_permanent_ability_words(scout, game.trigger_registry)
    game.fire_attack_triggers(scout)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == scout.obj_id
    assert isinstance(trigger.effect, ValiantEffect)


def test_corrupted_triggers_when_opponent_is_poisoned():
    """Corrupted fires when an opponent has three or more poison counters."""
    game, source = fresh_game_with_spell_cast_host(
        'Corrupted — Draw a card.',
        name='Infector',
    )
    game.players[1].poison = 3
    fire_test_instant_cast(game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id
