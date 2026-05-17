"""Unit tests for engine/rules/triggers.py."""

from engine.core.zones import Zone
from engine.rules.triggers import TriggerKey, TriggerRegistry, is_enters_battlefield
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_etb_trigger_goes_on_stack_from_zone_listener():
    """A registered ETB trigger fires when ZoneManager emits a matching event."""
    game = fresh_game()
    soul_warden = place_on_battlefield(
        make_creature("Soul Warden", 1, 1),
        0,
        game.zones,
    )
    registry = TriggerRegistry()
    registry.register(soul_warden, TriggerKey.ENTERS_BATTLEFIELD, is_enters_battlefield)
    game.zones.register_listener(
        lambda event: registry.put_triggers_on_stack(event, game)
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
    registry = TriggerRegistry()
    registry.register(soul_warden, TriggerKey.ENTERS_BATTLEFIELD, is_enters_battlefield)
    game.zones.register_listener(
        lambda event: registry.put_triggers_on_stack(event, game)
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
    registry = TriggerRegistry()
    registry.register(soul_warden, TriggerKey.ENTERS_BATTLEFIELD, is_enters_battlefield)
    game.zones.leave_battlefield(soul_warden, Zone.GRAVEYARD, "destroy")
    game.zones.register_listener(
        lambda event: registry.put_triggers_on_stack(event, game)
    )

    place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)

    assert game.stack.top is None
