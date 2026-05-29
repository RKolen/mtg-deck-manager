"""Shared helpers for ability-word unit tests."""

from __future__ import annotations

from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.core.game_object import CardObject, TriggeredAbilityOnStack
from engine.core.zones import Zone, ZoneMoveEvent
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def fire_source_etb(game, source) -> None:
    """Re-emit an ETB event after registering triggers (test helper)."""
    game.trigger_registry.put_triggers_on_stack(
        ZoneMoveEvent(
            obj=source,
            from_zone=Zone.HAND,
            to_zone=Zone.BATTLEFIELD,
            cause='test_etb',
            player_idx=source.controller_idx,
        ),
        game,
    )


def top_trigger(game) -> TriggeredAbilityOnStack:
    """Return the top stack trigger, asserting it is a triggered ability."""
    trigger = game.stack.top
    assert isinstance(trigger, TriggeredAbilityOnStack)
    return trigger


def fresh_game_with_spell_cast_host(
    oracle: str,
    *,
    name: str = 'Host',
):
    """Start a game with an ability-word host on the battlefield."""
    game = fresh_game()
    source = register_battlefield_ability_word_host(game, oracle, name=name)
    return game, source


def register_battlefield_ability_word_host(
    game,
    oracle: str,
    *,
    name: str = 'Host',
):
    """Place a creature with an ability word and register its triggers."""
    source = place_on_battlefield(
        make_creature(name, 1, 1, oracle=oracle),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    return source


def fire_test_instant_cast(game) -> CardObject:
    """Fire spell-cast triggers for a test instant."""
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Bolt'))
    game.fire_spell_cast_triggers(spell)
    return spell


def assert_source_etb_trigger(game, source) -> None:
    """Assert the source permanent's ETB trigger is on top of the stack."""
    fire_source_etb(game, source)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def assert_spell_cast_triggers_host(game, source) -> None:
    """Cast a test instant and assert the host's spell-cast trigger fired."""
    fire_test_instant_cast(game)
    trigger = top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id
