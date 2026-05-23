"""Unit tests for ability-word trigger registration and effects."""

from __future__ import annotations

from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.ability_words.clause import clause_after_ability_word
from engine.abilities.keywords.ability_words.effects import (
    AbilityWordEffect,
    ProwessEffect,
)
from engine.core.game_object import CardObject, Target, TriggeredAbilityOnStack
from engine.core.turn_structure import Step
from engine.core.zones import Zone, ZoneMoveEvent
from tests.conftest import (
    fresh_game,
    make_artifact,
    make_card,
    make_creature,
    make_instant,
    make_land,
    place_on_battlefield,
)


def _top_trigger(game):
    trigger = game.stack.top
    assert isinstance(trigger, TriggeredAbilityOnStack)
    return trigger


def test_clause_after_ability_word_parses_landfall_line():
    """Landfall clauses are extracted after the em dash."""
    oracle = "Landfall — You gain 2 life."
    assert clause_after_ability_word(oracle, "Landfall") == "You gain 2 life."


def test_landfall_triggers_when_controller_plays_land():
    """Landfall puts a trigger on the stack when a land enters."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Rampant Growth Host", 1, 1, oracle="Landfall — You gain 2 life."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    land = CardObject(controller_idx=0, owner_idx=0, card_info=make_land())
    game.zones.enter_battlefield(land, 0, "test", Zone.HAND)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_landfall_effect_gains_life_on_resolve():
    """Resolving a landfall trigger applies the parsed life clause."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Life Tracker", 1, 1, oracle="Landfall — You gain 2 life."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    land = CardObject(controller_idx=0, owner_idx=0, card_info=make_land())
    game.zones.enter_battlefield(land, 0, "test", Zone.HAND)
    trigger = _top_trigger(game)
    assert isinstance(trigger.effect, AbilityWordEffect)
    trigger.effect.resolve(game, trigger)
    assert game.players[0].life == 22


def test_constellation_triggers_on_enchantment_enter():
    """Constellation fires when an enchantment enters under your control."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Starfield Mystic", 2, 2, oracle="Constellation — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    enchantment = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_card(name="Aura", type_line="Enchantment", oracle=""),
    )
    game.zones.enter_battlefield(enchantment, 0, "test", Zone.HAND)
    assert game.stack.top is not None


def test_raid_triggers_at_beginning_of_combat_after_opponent_damaged():
    """Raid checks whether an opponent was dealt damage this turn."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature(
            "Raid Captain",
            2,
            2,
            oracle="Raid — Create a 1/1 red Goblin creature token.",
        ),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    game.mark_player_was_dealt_damage(1)
    game.fire_step_triggers(Step.BEGIN_COMBAT)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_magecraft_triggers_on_instant_cast():
    """Magecraft fires when you cast an instant or sorcery."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Veyran", 2, 2, oracle="Magecraft — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Bolt"))
    game.fire_spell_cast_triggers(spell)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_battalion_triggers_when_attacking_with_three_creatures():
    """Battalion fires once when three or more creatures attack."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Boros Elite", 3, 2, oracle="Battalion — It gets +2/+2 until end of turn."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    game.fire_mass_attack_triggers(0, 3)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def _fire_source_etb(game, source) -> None:
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


def test_metalcraft_triggers_on_etb_with_three_artifacts():
    """Metalcraft ETB abilities check artifact count on entry."""
    game = fresh_game()
    for _ in range(3):
        place_on_battlefield(make_artifact("Relic"), 0, game.zones)
    card = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature("Pia", 2, 2, oracle="Metalcraft — Draw a card."),
    )
    source = game.zones.enter_battlefield(card, 0, "test", Zone.HAND)
    register_permanent_ability_words(source, game.trigger_registry)
    _fire_source_etb(game, source)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_delirium_triggers_on_etb_with_four_graveyard_types():
    """Delirium ETB abilities check graveyard diversity on entry."""
    game = fresh_game()
    types = [
        make_creature("Bear", 2, 2),
        make_instant("Bolt"),
        make_artifact("Relic"),
        make_land("Swamp", "B"),
    ]
    for card_info in types:
        game.zones.player_zones[0].graveyard.append(
            CardObject(controller_idx=0, owner_idx=0, card_info=card_info),
        )
    card = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature("Grief", 2, 2, oracle="Delirium — Draw a card."),
    )
    source = game.zones.enter_battlefield(card, 0, "test", Zone.HAND)
    register_permanent_ability_words(source, game.trigger_registry)
    _fire_source_etb(game, source)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_morbid_triggers_on_spell_after_creature_dies():
    """Morbid fires when you cast a spell after a creature died this turn."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Gravecrawler Host", 1, 1, oracle="Morbid — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    doomed = place_on_battlefield(make_creature("Doomed", 1, 1), 0, game.zones)
    game.zones.leave_battlefield(doomed, Zone.GRAVEYARD, 'test', game)
    assert game.creature_died_this_turn
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Bolt"))
    game.fire_spell_cast_triggers(spell)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_ferocious_triggers_when_casting_with_power_four_creature():
    """Ferocious checks for a power-4+ creature you control."""
    game = fresh_game()
    place_on_battlefield(make_creature("Titan", 4, 5), 0, game.zones)
    source = place_on_battlefield(
        make_creature("Host", 1, 1, oracle="Ferocious — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Growth"))
    game.fire_spell_cast_triggers(spell)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_revolt_triggers_on_etb_after_permanent_left():
    """Revolt fires when this permanent enters after you had a revolt."""
    game = fresh_game()
    old = place_on_battlefield(make_creature("Sacrifice", 1, 1), 0, game.zones)
    game.zones.leave_battlefield(old, Zone.EXILE, 'test', game)
    assert game.players[0].revolt_this_turn
    card = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature("Renegade", 2, 1, oracle="Revolt — Draw a card."),
    )
    source = game.zones.enter_battlefield(card, 0, 'test', Zone.HAND)
    register_permanent_ability_words(source, game.trigger_registry)
    _fire_source_etb(game, source)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_rally_triggers_when_creature_enters():
    """Rally fires when a creature enters under your control."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Rally Leader", 1, 1, oracle="Rally — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    ally = CardObject(controller_idx=0, owner_idx=0, card_info=make_creature("Ally", 1, 1))
    game.zones.enter_battlefield(ally, 0, "test", Zone.HAND)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_hellbent_triggers_with_empty_hand():
    """Hellbent fires when you cast with no cards in hand."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Host", 1, 1, oracle="Hellbent — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    game.zones.player_zones[0].hand.clear()
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Bolt"))
    game.fire_spell_cast_triggers(spell)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_inspired_triggers_when_source_attacks():
    """Inspired fires when the source creature attacks."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Wind-Scarred", 2, 2, oracle="Inspired — Draw a card."),
        0,
        game.zones,
        sick=False,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    game.fire_attack_triggers(source)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_coven_triggers_with_three_distinct_powers():
    """Coven fires when you control three creatures with different powers."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Witch", 1, 1, oracle="Coven — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    for power in (1, 2, 3):
        place_on_battlefield(make_creature(f"P{power}", power, 1), 0, game.zones)
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Bolt"))
    game.fire_spell_cast_triggers(spell)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_strive_triggers_with_multiple_targets():
    """Strive fires when a spell is cast with two or more targets."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Host", 1, 1, oracle="Strive — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Bolt"))
    game.fire_spell_cast_triggers(
        spell,
        (Target(obj_id=1), Target(obj_id=2)),
    )
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_prowess_puts_counter_when_trigger_resolves():
    """Prowess adds a +1/+1 counter to the source permanent."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Monastery Swiftspear", 1, 2, oracle="Prowess"),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Growth"))
    game.fire_spell_cast_triggers(spell)
    trigger = _top_trigger(game)
    assert isinstance(trigger.effect, ProwessEffect)
    trigger.effect.resolve(game, trigger)
    assert source.counters.get("+1/+1") == 1


def test_fateful_hour_triggers_at_low_life():
    """Fateful hour fires when the controller has 5 or less life."""
    game = fresh_game(player_life=5)
    source = place_on_battlefield(
        make_creature("Zealot", 2, 2, oracle="Fateful hour — You gain 2 life."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Bolt"))
    game.fire_spell_cast_triggers(spell)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_descend_triggers_with_four_permanents_in_graveyard():
    """Descend fires with four or more permanent cards in the graveyard."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Diver", 2, 2, oracle="Descend — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    for idx in range(4):
        game.zones.player_zones[0].graveyard.append(
            CardObject(
                controller_idx=0,
                owner_idx=0,
                card_info=make_artifact(f"Rock {idx}"),
            ),
        )
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Bolt"))
    game.fire_spell_cast_triggers(spell)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_survival_triggers_after_creature_dies():
    """Survival fires after a creature died this turn."""
    game = fresh_game()
    game.creature_died_this_turn = True
    source = place_on_battlefield(
        make_creature("Survivor", 2, 2, oracle="Survival — Draw a card."),
        0,
        game.zones,
    )
    register_permanent_ability_words(source, game.trigger_registry)
    spell = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant("Bolt"))
    game.fire_spell_cast_triggers(spell)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id


def test_underdog_triggers_when_outnumbered():
    """Underdog fires when attacking with fewer creatures than an opponent."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature("Underdog", 2, 2, oracle="Underdog — Draw a card."),
        0,
        game.zones,
        sick=False,
    )
    place_on_battlefield(make_creature("Big", 4, 4), 1, game.zones)
    place_on_battlefield(make_creature("Bigger", 5, 5), 1, game.zones)
    register_permanent_ability_words(source, game.trigger_registry)
    game.fire_attack_triggers(source)
    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == source.obj_id
