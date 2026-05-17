"""Unit tests for engine/rules/triggers.py."""

from engine.core.zones import Zone
from engine.rules.triggers import TriggerKey, is_dies, is_enters_battlefield
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

    trigger = game.stack.top
    assert trigger is not None
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

    trigger = game.stack.top
    assert trigger is not None
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

    trigger = game.stack.top
    assert trigger is not None
    assert trigger.source_permanent_id == doomed.obj_id
    assert trigger.controller_idx == 0
    assert trigger.trigger_key == TriggerKey.DIES.value
