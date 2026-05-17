"""Unit tests for engine/rules/triggers.py."""

from engine.core.game_object import TriggeredAbilityOnStack
from engine.core.game_state import GameState
from engine.core.turn_structure import Step
from engine.core.zones import Zone
from engine.rules.triggers import TriggerKey, is_attacks, is_beginning_of_upkeep, is_dies
from engine.rules.triggers import is_blocks, is_enters_battlefield
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_etb_trigger_goes_on_stack_from_game_state_listener():
    """A registered ETB trigger fires from GameState's zone listener."""
    game = fresh_game()
    soul_warden = place_on_battlefield(
        make_creature("Soul Warden", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        soul_warden,
        TriggerKey.ENTERS_BATTLEFIELD,
        is_enters_battlefield,
    )

    place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == soul_warden.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.ENTERS_BATTLEFIELD.value


def test_etb_condition_ignores_non_battlefield_moves():
    """ETB conditions do not fire for unrelated zone moves."""
    game = fresh_game()
    soul_warden = place_on_battlefield(
        make_creature("Soul Warden", 1, 1),
        0,
        game.zones,
    )
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)
    game.trigger_registry.register(
        soul_warden,
        TriggerKey.ENTERS_BATTLEFIELD,
        is_enters_battlefield,
    )

    game.zones.leave_battlefield(bear, Zone.GRAVEYARD, "destroy")

    assert game.stack.top is None


def test_trigger_does_not_fire_after_source_left_battlefield():
    """Registered triggers stop firing when their source permanent is gone."""
    game = fresh_game()
    soul_warden = place_on_battlefield(
        make_creature("Soul Warden", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        soul_warden,
        TriggerKey.ENTERS_BATTLEFIELD,
        is_enters_battlefield,
    )
    game.zones.leave_battlefield(soul_warden, Zone.GRAVEYARD, "destroy")

    place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)

    assert game.stack.top is None


def test_dies_trigger_goes_on_stack_from_sba_death():
    """A registered dies trigger fires when a creature dies from SBAs."""
    game = fresh_game()
    blood_artist = place_on_battlefield(
        make_creature("Blood Artist", 0, 1),
        0,
        game.zones,
    )
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)
    game.trigger_registry.register(blood_artist, TriggerKey.DIES, is_dies)

    bear.damage_marked = 2
    game.check_sbas()

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == blood_artist.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.DIES.value


def test_self_dies_trigger_fires_from_own_sba_death():
    """Dies triggers can fire from the source permanent leaving battlefield."""
    game = fresh_game()
    doomed = place_on_battlefield(
        make_creature("Doomed Traveler", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(doomed, TriggerKey.DIES, is_dies)

    doomed.damage_marked = 1
    game.check_sbas()

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == doomed.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.DIES.value


def test_upkeep_trigger_goes_on_stack_from_step_event():
    """Beginning-of-upkeep triggers fire from explicit step events."""
    game = fresh_game()
    shrine = place_on_battlefield(
        make_creature("Shrine Keeper", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        shrine,
        TriggerKey.BEGINNING_OF_UPKEEP,
        is_beginning_of_upkeep,
    )

    game.fire_step_triggers(Step.UPKEEP)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == shrine.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.BEGINNING_OF_UPKEEP.value


def test_upkeep_trigger_does_not_fire_during_draw_step():
    """Beginning-of-upkeep triggers ignore other beginning-phase steps."""
    game = fresh_game()
    shrine = place_on_battlefield(
        make_creature("Shrine Keeper", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(
        shrine,
        TriggerKey.BEGINNING_OF_UPKEEP,
        is_beginning_of_upkeep,
    )

    game.fire_step_triggers(Step.DRAW)

    assert game.stack.top is None


def test_attack_trigger_goes_on_stack_from_declared_attacker():
    """Attack triggers fire when an attacker is declared."""
    game = fresh_game()
    raider = place_on_battlefield(
        make_creature("Raid Captain", 2, 2),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(
        make_creature("Goblin", 1, 1),
        0,
        game.zones,
    )
    game.trigger_registry.register(raider, TriggerKey.ATTACKS, is_attacks)

    game.fire_attack_triggers(attacker)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == raider.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.ATTACKS.value


def test_attack_trigger_does_not_fire_from_upkeep_event():
    """Attack triggers ignore unrelated step events."""
    game = fresh_game()
    raider = place_on_battlefield(
        make_creature("Raid Captain", 2, 2),
        0,
        game.zones,
    )
    game.trigger_registry.register(raider, TriggerKey.ATTACKS, is_attacks)

    game.fire_step_triggers(Step.UPKEEP)

    assert game.stack.top is None


def test_block_trigger_goes_on_stack_from_declared_blocker():
    """Block triggers fire when a blocker is declared."""
    game = fresh_game()
    sentry = place_on_battlefield(
        make_creature("Sentry", 1, 4),
        0,
        game.zones,
    )
    blocker = place_on_battlefield(
        make_creature("Wall", 0, 4),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(
        make_creature("Goblin", 2, 2),
        1,
        game.zones,
    )
    game.trigger_registry.register(sentry, TriggerKey.BLOCKS, is_blocks)

    game.fire_block_triggers(blocker, attacker)

    trigger = _top_trigger(game)
    assert trigger.source_permanent_id == sentry.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.BLOCKS.value


def test_block_trigger_does_not_fire_from_attack_event():
    """Block triggers ignore attack declaration events."""
    game = fresh_game()
    sentry = place_on_battlefield(
        make_creature("Sentry", 1, 4),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(
        make_creature("Goblin", 2, 2),
        1,
        game.zones,
    )
    game.trigger_registry.register(sentry, TriggerKey.BLOCKS, is_blocks)

    game.fire_attack_triggers(attacker)

    assert game.stack.top is None


def _top_trigger(game: GameState) -> TriggeredAbilityOnStack:
    """Return the stack top narrowed for Pylance."""
    trigger = game.stack.top
    assert isinstance(trigger, TriggeredAbilityOnStack)
    return trigger
