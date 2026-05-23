"""Integration tests for activated keywords in the game loop."""

from engine.core.game_object import CardObject
from engine.game import create_game
from tests.conftest import make_card, make_creature, make_deck, make_instant, place_on_battlefield


def test_cycle_draws_a_card():
    """Cycling from hand discards and draws."""
    cycler = make_instant("Street Wraith", oracle="Cycling {0}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=cycler),
    ]
    hand_before = len(game.state.zones.player_zones[0].hand)
    data = game.action_cycle(0)
    assert "error" not in data
    assert len(game.state.zones.player_zones[0].hand) == hand_before
    assert len(game.state.zones.player_zones[0].graveyard) == 1


def test_unearth_creature_enters_battlefield():
    """Unearth returns a creature from the graveyard."""
    crawler = make_creature("Gravecrawler", oracle="Unearth {0}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].graveyard = [
        CardObject(controller_idx=0, owner_idx=0, card_info=crawler),
    ]
    data = game.action_unearth(0)
    assert "error" not in data
    assert len(game.state.zones.battlefield) == 1


def test_activate_draw_ability_on_stack():
    """A generic tap ability draws after the stack resolves."""
    sage = make_creature("Archivist", oracle="{T}: Draw a card.")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    sage_perm = place_on_battlefield(sage, 0, game.state.zones, sick=False)
    hand_before = len(game.state.zones.player_zones[0].hand)
    data = game.action_activate(str(sage_perm.obj_id), 0)
    assert "error" not in data
    assert not game.state.stack.is_empty
    game.action_pass_priority()
    game.action_pass_priority()
    assert game.state.stack.is_empty
    assert len(game.state.zones.player_zones[0].hand) == hand_before + 1


def test_crew_vehicle_in_combat():
    """A crewed vehicle can be declared as an attacker."""
    vehicle_info = make_card(
        name="Sky Skiff",
        type_line="Artifact — Vehicle",
        pt="3/3",
        oracle="Crew 1",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    vehicle = place_on_battlefield(vehicle_info, 0, game.state.zones)
    crewer = place_on_battlefield(make_creature("Soldier", 1, 1), 0, game.state.zones)
    data = game.action_crew(str(vehicle.obj_id), [str(crewer.obj_id)])
    assert "error" not in data
    game.action_go_to_attack()
    data = game.action_toggle_attacker(str(vehicle.obj_id))
    assert "error" not in data
