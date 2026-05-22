"""Integration tests for Phase E keyword behaviour in the game loop."""

from engine.core.game_object import CardObject
from engine.game import create_game
from engine.rules.combat import can_attack
from tests.conftest import make_card, make_creature, make_deck, make_instant, place_on_battlefield


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


def test_flashback_cast_from_graveyard_exiles_on_resolve():
    """Flashback removes the card from the graveyard and exiles it after resolving."""
    shock = make_instant(
        name="Shock",
        oracle="Shock deals 2 damage to any target.\nFlashback {0}",
        mana_cost="{R}",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    card = CardObject(controller_idx=0, owner_idx=0, card_info=shock)
    game.state.zones.player_zones[0].graveyard.append(card)
    data = game.action_cast_flashback(0, target_player=1)
    assert data["opponentLife"] == 18
    assert not data["stack"]
    assert len(game.state.zones.player_zones[0].graveyard) == 0
    assert len(game.state.zones.player_zones[0].exile) == 1
    assert game.state.zones.player_zones[0].exile[0].card_info.name == "Shock"


def test_kicked_burn_spell_deals_extra_damage():
    """A kicked burn spell pays the kicker cost and uses kicked damage."""
    burst = make_instant(
        name="Burst Lightning",
        cmc=0,
        mana_cost="",
        oracle=(
            "Burst Lightning deals 2 damage to any target. "
            "Kicker {0}. If this spell was kicked, it deals 4 damage instead."
        ),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=burst),
    ]
    without = game.action_cast(0, target_player=1, kicker_times=0)
    assert without["opponentLife"] == 18

    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=burst),
    ]
    with_kicker = game.action_cast(0, target_player=1, kicker_times=1)
    assert with_kicker["opponentLife"] == 16
