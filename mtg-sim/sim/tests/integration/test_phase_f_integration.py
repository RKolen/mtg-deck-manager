"""Integration tests for Phase F layers and replacement effects in the game loop."""

from engine.core.game_object import CardObject
from engine.game import create_game
from tests.conftest import (
    _CardStats,
    make_artifact,
    make_card,
    make_creature,
    make_deck,
    make_instant,
    make_land,
    place_on_battlefield,
    put_lands_on_battlefield,
    set_player_hand_single,
)


def test_absorb_reduces_shock_damage_in_game_loop():
    """Absorb on a creature reduces spell damage before SBAs run."""
    shock = make_instant(
        "Shock",
        mana_cost="{R}",
        oracle="Shock deals 2 damage to any target.",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    ward = place_on_battlefield(
        make_creature("Loxodon", 2, 5, oracle="Absorb 2"),
        0,
        game.state.zones,
    )
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    set_player_hand_single(game, shock)
    data = game.action_cast(0, target_uid=str(ward.obj_id))
    assert "error" not in data
    assert ward in game.state.zones.battlefield
    assert ward.damage_marked == 0


def test_absorb_reduces_combat_damage_when_blocking():
    """Absorb reduces combat damage assigned during the opponent attack step."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    blocker = place_on_battlefield(
        make_creature("Loxodon", 2, 3, oracle="Absorb 2"),
        0,
        game.state.zones,
        sick=False,
    )
    attacker = place_on_battlefield(
        make_creature("Raider", 3, 3),
        1,
        game.state.zones,
        sick=False,
    )
    game.action_end_turn()
    game.action_assign_blocker(str(blocker.obj_id), str(attacker.obj_id))
    data = game.action_confirm_blocks()
    assert data["phase"] == "draw"
    assert blocker.damage_marked == 1
    assert attacker.damage_marked == 2


def test_hexproof_from_instants_blocks_opponent_shock():
    """Hexproof from instants causes burn to fizzle when targeting is illegal."""
    shock = make_instant(
        "Shock",
        cmc=0,
        mana_cost="",
        oracle="Shock deals 2 damage to any target.",
    )
    game = create_game([shock for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    ward = place_on_battlefield(
        make_creature("Slippery", 2, 2, oracle="Hexproof from instants"),
        1,
        game.state.zones,
    )
    data = game.action_cast(0, target_uid=str(ward.obj_id))
    assert not data["stack"]
    assert ward.damage_marked == 0
    assert ward in game.state.zones.battlefield


def test_living_metal_artifact_attacks_for_three_damage():
    """Living metal artifacts animate during combat and deal damage."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    golem = place_on_battlefield(
        make_artifact("Golem", cmc=3, oracle="Living metal"),
        0,
        game.state.zones,
        sick=False,
    )
    game.action_go_to_attack()
    game.action_toggle_attacker(str(golem.obj_id))
    data = game.action_confirm_attack()
    assert data["opponentLife"] == 17
    assert golem in game.state.zones.battlefield
    assert golem.counters.get("living_metal", 0) == 0
    assert golem.counters.get("+1/+1", 0) == 0


def test_shield_counter_prevents_shock_damage_in_game_loop():
    """A shield counter is removed instead of marking damage from a burn spell."""
    shock = make_instant(
        "Shock",
        cmc=0,
        mana_cost="",
        oracle="Shock deals 2 damage to any target.",
    )
    game = create_game([shock for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    defender = place_on_battlefield(make_creature("Defender", 2, 2), 0, game.state.zones)
    defender.counters["shield"] = 1
    data = game.action_cast(0, target_uid=str(defender.obj_id))
    assert "error" not in data
    assert defender in game.state.zones.battlefield
    assert defender.damage_marked == 0
    assert defender.counters.get("shield", 0) == 0


def test_humility_allows_shock_to_target_hexproof_creature():
    """Humility strips hexproof so burn can remove a creature in the game loop."""
    shock = make_instant(
        "Shock",
        cmc=0,
        mana_cost="",
        oracle="Shock deals 2 damage to any target.",
    )
    humility = make_card(
        name="Humility",
        type_line="Enchantment",
        oracle=(
            "All creatures lose all abilities and have base power and toughness 1/1."
        ),
    )
    game = create_game([shock for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    place_on_battlefield(humility, 0, game.state.zones)
    slippery = place_on_battlefield(
        make_creature("Slippery", 5, 5, oracle="Hexproof"),
        1,
        game.state.zones,
    )
    data = game.action_cast(0, target_uid=str(slippery.obj_id))
    assert "error" not in data
    assert slippery not in game.state.zones.battlefield


def test_rest_in_peace_exiles_creature_destroyed_by_shock():
    """Rest in Peace replaces graveyard with exile when a creature dies."""
    shock = make_instant(
        "Shock",
        cmc=0,
        mana_cost="",
        oracle="Shock deals 2 damage to any target.",
    )
    rip = make_card(
        name="Rest in Peace",
        type_line="Enchantment",
        oracle="If a card would be put into a graveyard, exile it instead.",
    )
    game = create_game([shock for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    place_on_battlefield(rip, 0, game.state.zones)
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 1, game.state.zones)
    data = game.action_cast(0, target_uid=str(bear.obj_id))
    assert "error" not in data
    assert bear not in game.state.zones.battlefield
    assert len(game.state.zones.player_zones[1].graveyard) == 0
    assert len(game.state.zones.player_zones[1].exile) == 1


def test_umbra_armor_saves_creature_from_lethal_shock():
    """Umbra armor exiles the aura instead of the enchanted creature dying."""
    shock = make_instant(
        "Shock",
        cmc=0,
        mana_cost="",
        oracle="Shock deals 2 damage to any target.",
    )
    game = create_game([shock for _ in range(20)], make_deck(lands=20))
    game.action_keep()
    bearer = place_on_battlefield(make_creature("Bearer", 2, 2), 0, game.state.zones)
    aura = place_on_battlefield(
        make_card(
            name="Shield",
            type_line="Enchantment — Aura",
            oracle="Umbra armor\nEnchant creature",
            mana_cost="{W}",
            stats=_CardStats(cmc=1.0, pt="0/0"),
        ),
        0,
        game.state.zones,
    )
    aura.attached_to = bearer.obj_id
    data = game.action_cast(0, target_uid=str(bearer.obj_id))
    assert "error" not in data
    assert bearer in game.state.zones.battlefield
    assert bearer.damage_marked == 0
    assert aura not in game.state.zones.battlefield
    assert len(game.state.zones.player_zones[0].exile) == 1


def test_regeneration_shield_survives_lethal_shock():
    """Regenerate replaces destruction from lethal spell damage."""
    renew = make_instant("Renew", cmc=0, mana_cost="", oracle="Regenerate target creature.")
    shock = make_instant(
        "Shock",
        cmc=0,
        mana_cost="",
        oracle="Shock deals 2 damage to any target.",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    troll = place_on_battlefield(make_creature("Troll", 2, 2), 0, game.state.zones)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=renew),
        CardObject(controller_idx=0, owner_idx=0, card_info=shock),
    ]
    data = game.action_cast(0, target_uid=str(troll.obj_id))
    assert "error" not in data
    data = game.action_cast(0, target_uid=str(troll.obj_id))
    assert "error" not in data
    assert troll in game.state.zones.battlefield
    assert troll.damage_marked == 0
