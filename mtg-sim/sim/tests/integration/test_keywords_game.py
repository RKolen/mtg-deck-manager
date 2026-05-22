"""Integration tests for Phase E keyword behaviour in the game loop."""

from engine.core.game_object import CardObject
from engine.core.zones import Zone
from engine.game import create_game
from engine.rules.combat import can_attack
from tests.conftest import (
    make_card,
    make_creature,
    make_deck,
    make_instant,
    make_land,
    place_on_battlefield,
)


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


def test_storm_spell_creates_and_resolves_copies():
    """Storm puts one copy on the stack per other spell cast this turn."""
    grapeshot = make_instant(
        name="Grapeshot",
        cmc=0,
        mana_cost="",
        oracle="Grapeshot deals 1 damage to any target. Storm",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.players[0].spells_cast_this_turn = 2
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=grapeshot),
    ]
    data = game.action_cast(0, target_player=1)
    assert data["opponentLife"] == 17
    assert len(game.state.zones.player_zones[0].graveyard) == 1


def test_cascade_casts_free_spell_from_library():
    """Casting a cascade spell puts a lower-mana hit on the stack and resolves it."""
    hit = make_instant(
        name="Hit",
        cmc=1,
        mana_cost="",
        oracle="Hit deals 1 damage to any target.",
    )
    boarder = make_instant(
        name="Boarder",
        cmc=4,
        mana_cost="",
        oracle="Boarder has no effect. Cascade",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    for _ in range(4):
        land = CardObject(controller_idx=0, owner_idx=0, card_info=make_land())
        game.state.zones.enter_battlefield(land, 0, "test_setup", Zone.HAND)
    game.state.zones.player_zones[0].library = [
        CardObject(controller_idx=0, owner_idx=0, card_info=make_land()),
        CardObject(controller_idx=0, owner_idx=0, card_info=hit),
    ]
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=boarder),
    ]
    data = game.action_cast(0, target_player=1)
    assert data["opponentLife"] == 19
    assert len(game.state.zones.player_zones[0].library) == 1


def test_convoke_cast_taps_creatures_to_pay_mana():
    """Convoke lets a 4-mana burn spell be paid with two tapped creatures and two lands."""
    burn = make_instant(
        name="Mob Justice",
        cmc=4,
        mana_cost="",
        oracle="Mob Justice deals 4 damage to any target. Convoke",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    for _ in range(2):
        land = CardObject(controller_idx=0, owner_idx=0, card_info=make_land())
        game.state.zones.enter_battlefield(land, 0, "test_setup", Zone.HAND)
    soldier = place_on_battlefield(make_creature("Soldier", 1, 1), 0, game.state.zones)
    knight = place_on_battlefield(make_creature("Knight", 1, 1), 0, game.state.zones)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=burn),
    ]
    data = game.action_cast(
        0,
        target_player=1,
        convoke_creature_ids=[soldier.obj_id, knight.obj_id],
    )
    assert data["opponentLife"] == 16
    assert soldier.tapped
    assert knight.tapped
