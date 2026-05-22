"""Integration tests for Phase E keyword behaviour in the game loop."""

from engine.game import create_game
from engine.rules.combat import can_attack
from tests.conftest import make_creature, make_deck, place_on_battlefield


def test_haste_creature_can_attack_same_turn_it_entered():
    """A haste creature is not summoning-sick when it enters the battlefield."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    hasty = place_on_battlefield(
        make_creature("Goblin Bushwhacker", 1, 1, oracle="Haste"),
        0,
        game.state.zones,
    )
    assert can_attack(hasty)
