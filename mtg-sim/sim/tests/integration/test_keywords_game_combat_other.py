"""Integration tests for ability_other combat keywords in the game loop."""

from engine.core.game_object import CardObject
from engine.core.mana import mana_of
from engine.game import create_game
from tests.conftest import (
    make_creature,
    make_deck,
    make_land,
    place_on_battlefield,
    put_lands_on_battlefield,
)


def test_bushido_puts_counter_when_creature_blocks():
    """Bushido adds +1/+1 when the creature becomes engaged in blocked combat."""
    samurai = make_creature("Samurai", 2, 2, oracle="Bushido 1")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    blocker = place_on_battlefield(samurai, 0, game.state.zones, sick=False)
    attacker = place_on_battlefield(make_creature("Goblin", 2, 2), 1, game.state.zones, sick=False)
    game.action_end_turn()
    game.action_assign_blocker(str(blocker.obj_id), str(attacker.obj_id))
    data = game.action_confirm_blocks()
    assert "error" not in data
    assert blocker.counters.get("+1/+1") == 1


def test_toxic_adds_poison_on_unblocked_attack():
    """Toxic gives poison counters when combat damage is dealt to a player."""
    rat = make_creature("Rat", 1, 1, oracle="Toxic 1")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    rat_perm = place_on_battlefield(rat, 0, game.state.zones, sick=False)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(rat_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert game.state.players[1].poison == 1


def test_ingest_exiles_library_card_on_attack():
    """Ingest exiles the top card of the damaged player's library."""
    ingestor = make_creature("Ingestor", 2, 2, oracle="Ingest")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    library_before = len(game.state.zones.player_zones[1].library)
    ingestor_perm = place_on_battlefield(ingestor, 0, game.state.zones, sick=False)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(ingestor_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert len(game.state.zones.player_zones[1].library) == library_before - 1
    assert len(game.state.zones.player_zones[1].exile) == 1


def test_battle_cry_buffs_other_attackers():
    """Battle cry grants +1/+0 to other attacking creatures you control."""
    crier = make_creature("Crier", 2, 2, oracle="Battle cry")
    soldier = make_creature("Soldier", 1, 1)
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    crier_perm = place_on_battlefield(crier, 0, game.state.zones, sick=False)
    soldier_perm = place_on_battlefield(soldier, 0, game.state.zones, sick=False)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(crier_perm.obj_id))
    game.action_toggle_attacker(str(soldier_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert soldier_perm.counters.get("battle_cry") == 1


def test_melee_draws_with_three_attackers():
    """Melee with a draw clause draws when three creatures attack."""
    veteran = make_creature("Veteran", 2, 2, oracle="Melee — Draw a card.")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    attackers = [
        place_on_battlefield(make_creature(f"Unit{i}", 1, 1), 0, game.state.zones, sick=False)
        for i in range(2)
    ]
    veteran_perm = place_on_battlefield(veteran, 0, game.state.zones, sick=False)
    hand_before = len(game.state.zones.player_zones[0].hand)
    game.action_go_to_attack()
    for perm in (*attackers, veteran_perm):
        game.action_toggle_attacker(str(perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert len(game.state.zones.player_zones[0].hand) == hand_before + 1


def test_dethrone_draws_when_attacking_highest_life_player():
    """Dethrone draws a card when damage hits the player with the most life."""
    queen = make_creature(
        "Queen",
        3,
        3,
        oracle="Dethrone\nWhenever this creature deals combat damage to a player, draw a card.",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    queen_perm = place_on_battlefield(queen, 0, game.state.zones, sick=False)
    hand_before = len(game.state.zones.player_zones[0].hand)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(queen_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert len(game.state.zones.player_zones[0].hand) == hand_before + 1


def test_sunburst_puts_counters_from_mana_pool_on_cast():
    """Sunburst adds +1/+1 counters for each color in the mana pool on ETB."""
    core = make_creature("Core", 0, 0, oracle="Sunburst", mana_cost="{G}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.players[0].mana_pool.add(mana_of("R"), mana_of("U"), mana_of("G"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=core),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    core_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Core")
    assert core_perm.counters.get("+1/+1") == 2


def test_echo_marks_creature_on_cast():
    """Echo marks a creature that will owe echo at the next upkeep."""
    shriek = make_creature("Shrieker", 2, 2, oracle="Echo {1}{G}", mana_cost="{2}{G}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 3, land_info=make_land("Forest", "G"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=shriek),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    shriek_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Shrieker")
    assert shriek_perm.counters.get("echo") == 1
