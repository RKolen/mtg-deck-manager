"""Unit tests for keyword actions batch 10.

Activate, Airbend, Earthbend, Waterbend, Convert, and Plot.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.specialty import (
    activate_keyword_action,
    bend_creature,
    has_activate_action,
    has_airbend,
    has_convert,
    has_earthbend,
    has_plot_action,
    has_waterbend,
    plot_keyword_action,
    transform_creature,
)
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_activate_keyword_action_taps_permanent():
    """Activate taps the target permanent."""
    game = fresh_game()
    monolith = place_on_battlefield(make_creature('Monolith', 0, 4), 0, game.zones)
    assert has_activate_action('Activate.')
    detail = activate_keyword_action(game.zones, str(monolith.obj_id))
    assert detail is not None
    assert monolith.tapped


def test_airbend_puts_airbend_counter_on_creature():
    """Airbend adds an airbend counter to the target creature."""
    game = fresh_game()
    monk = place_on_battlefield(make_creature('Monk', 2, 2), 0, game.zones)
    assert has_airbend('Airbend.')
    detail = bend_creature(game.zones, str(monk.obj_id), 'airbend')
    assert detail is not None
    assert monk.counters.get('airbend') == 1


def test_earthbend_puts_earthbend_counter_on_creature():
    """Earthbend adds an earthbend counter to the target creature."""
    game = fresh_game()
    bender = place_on_battlefield(make_creature('Bender', 3, 3), 0, game.zones)
    assert has_earthbend('Earthbend.')
    detail = bend_creature(game.zones, str(bender.obj_id), 'earthbend')
    assert detail is not None
    assert bender.counters.get('earthbend') == 1


def test_waterbend_puts_waterbend_counter_on_creature():
    """Waterbend adds a waterbend counter to the target creature."""
    game = fresh_game()
    sailor = place_on_battlefield(make_creature('Sailor', 1, 3), 0, game.zones)
    assert has_waterbend('Waterbend.')
    detail = bend_creature(game.zones, str(sailor.obj_id), 'waterbend')
    assert detail is not None
    assert sailor.counters.get('waterbend') == 1


def test_convert_transforms_creature_face_state():
    """Convert toggles a creature between face-up and face-down."""
    game = fresh_game()
    werewolf = place_on_battlefield(make_creature('Wolf', 4, 4), 0, game.zones)
    assert has_convert('Convert.')
    assert not werewolf.face_down
    detail = transform_creature(game.zones, str(werewolf.obj_id))
    assert detail is not None
    assert werewolf.face_down


def test_plot_keyword_action_logs_plotting():
    """Plot keyword action logs a simplified plot resolution."""
    oracle = 'Plot — You may cast this spell from exile.'
    assert has_plot_action(oracle)
    detail = plot_keyword_action()
    assert detail == 'plotted (keyword action)'
