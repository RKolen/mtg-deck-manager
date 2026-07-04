"""Integration tests for ability_other keywords in the game loop."""

from engine.core.game_object import CardObject
from engine.game import create_game
from tests.conftest import (
    _CardStats,
    cast_announce_options,
    make_artifact,
    make_card,
    make_creature,
    make_deck,
    make_instant,
    make_land,
    place_on_battlefield,
    put_lands_on_battlefield,
)

_CASUALTY_SHOCK_ORACLE = (
    "Casualty 2 (As an additional cost to cast this spell, you may sacrifice "
    "a creature with power 2 or greater. When you do, copy this spell and you "
    "may choose new targets for the copy.)\n"
    "Shock deals 2 damage to any target."
)
_CRAFT_ORACLE = (
    "{2}, Exile three artifacts you control: Craft this artifact "
    "into a creature."
)


def test_scavenge_from_graveyard_puts_counters_on_creature():
    """Scavenge exiles a graveyard creature and puts +1/+1 counters on a target."""
    scavenger = make_creature("Snap", 3, 2, oracle="Scavenge {2}{G}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    target = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.state.zones, sick=False)
    put_lands_on_battlefield(game, 3, land_info=make_land("Forest", "G"))
    game.state.zones.player_zones[0].graveyard = [
        CardObject(controller_idx=0, owner_idx=0, card_info=scavenger),
    ]
    data = game.action_scavenge(0, str(target.obj_id))
    assert "error" not in data
    assert len(game.state.zones.player_zones[0].graveyard) == 0
    assert len(game.state.zones.player_zones[0].exile) == 1
    assert target.counters.get("+1/+1") == 3


def test_craft_exiles_artifacts_in_game_loop():
    """Craft activation exiles artifacts and marks the host permanent crafted."""
    host = make_card(
        "Clay Statue",
        type_line="Artifact",
        oracle=_CRAFT_ORACLE,
        stats=_CardStats(cmc=2.0, pt="0/0"),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    host_perm = place_on_battlefield(host, 0, game.state.zones)
    relic = place_on_battlefield(make_artifact("Relic"), 0, game.state.zones)
    put_lands_on_battlefield(game, 2)
    data = game.action_craft(str(host_perm.obj_id), [str(relic.obj_id)])
    assert "error" not in data
    assert host_perm.counters.get("crafted") == 1
    assert len(game.state.zones.player_zones[0].exile) == 1


def test_casualty_cast_copies_spell_on_stack():
    """Paying casualty sacrifices a creature and copies the spell on the stack."""
    shock = make_instant(
        "Shock",
        cmc=1,
        mana_cost="{R}",
        oracle=_CASUALTY_SHOCK_ORACLE,
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    fodder = place_on_battlefield(make_creature("Fodder", 2, 2), 0, game.state.zones)
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=shock),
    ]
    data = game.action_cast(
        0,
        target_player=1,
        cast_options=cast_announce_options(
            paid_casualty=True,
            casualty_sacrifice_ids=[fodder.obj_id],
        ),
    )
    assert "error" not in data
    assert fodder.source in game.state.zones.player_zones[0].graveyard
    assert data["opponentLife"] == 16


def test_affinity_creature_casts_with_one_fewer_land():
    """Affinity for artifacts reduces the mana needed to cast from hand."""
    enforcer = make_card(
        "Myr Enforcer",
        type_line="Artifact Creature — Myr",
        oracle="Affinity for artifacts",
        mana_cost="{3}",
        stats=_CardStats(cmc=3.0, pt="1/1"),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    place_on_battlefield(make_artifact("Relic"), 0, game.state.zones)
    put_lands_on_battlefield(game, 2)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=enforcer),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    assert any(perm.name == "Myr Enforcer" for perm in game.state.zones.battlefield)


def test_afterlife_creates_spirits_when_creature_dies():
    """Afterlife creates Spirit tokens when the creature dies in the game loop."""
    shock = make_instant("Shock", mana_cost="{R}", oracle="Shock deals 2 damage to any target.")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    victim = place_on_battlefield(
        make_creature("Orzhov", 2, 2, oracle="Afterlife 2"),
        0,
        game.state.zones,
    )
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=shock),
    ]
    data = game.action_cast(0, target_uid=str(victim.obj_id))
    assert "error" not in data
    spirits = [perm for perm in game.state.zones.battlefield if "Spirit" in perm.type_line]
    assert len(spirits) == 2


def test_convoke_cast_taps_creatures_to_reduce_mana():
    """Convoke lets a spell tap creatures to pay generic mana in the game loop."""
    burn = make_instant(
        name="Mob Justice",
        cmc=4,
        mana_cost="",
        oracle="Mob Justice deals 4 damage to any target. Convoke",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 2)
    soldier = place_on_battlefield(make_creature("Soldier", 1, 1), 0, game.state.zones)
    knight = place_on_battlefield(make_creature("Knight", 1, 1), 0, game.state.zones)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=burn),
    ]
    data = game.action_cast(
        0,
        target_player=1,
        cast_options=cast_announce_options(
            convoke_creature_ids=[soldier.obj_id, knight.obj_id],
        ),
    )
    assert "error" not in data
    assert data["opponentLife"] == 16
    assert soldier.tapped
    assert knight.tapped


def test_evoke_cast_sacrifices_creature_on_resolve():
    """Casting for evoke sacrifices the creature when it enters the battlefield."""
    mulldrifter = make_creature(
        "Mulldrifter",
        2,
        2,
        mana_cost="{4}{U}",
        oracle="Flying\nEvoke {2}{U}",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 3, land_info=make_land("Island", "U"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=mulldrifter),
    ]
    data = game.action_cast(0, cast_options=cast_announce_options(cast_for_evoke=True))
    assert "error" not in data
    assert not any(perm.name == "Mulldrifter" for perm in game.state.zones.battlefield)
    assert len(game.state.zones.player_zones[0].graveyard) == 1


def test_exploit_sacrifices_creature_on_etb_in_game_loop():
    """Exploit sacrifices another creature when the exploiter enters."""
    exploiter = make_creature("Marchesa", 3, 3, oracle="Exploit", mana_cost="{2}{B}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    fodder = place_on_battlefield(make_creature("Fodder", 1, 1), 0, game.state.zones)
    put_lands_on_battlefield(game, 3, land_info=make_land("Swamp", "B"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=exploiter),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    assert fodder.source in game.state.zones.player_zones[0].graveyard
    assert any(perm.name == "Marchesa" for perm in game.state.zones.battlefield)


def test_evolve_puts_counter_when_larger_creature_enters():
    """Evolve triggers when a larger creature enters under your control."""
    evolver = make_creature("Shambleshark", 1, 1, oracle="Evolve", mana_cost="{G}")
    bigger = make_creature("Ripjaw", 4, 4, mana_cost="{3}{G}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=evolver),
        CardObject(controller_idx=0, owner_idx=0, card_info=bigger),
    ]
    put_lands_on_battlefield(game, 5, land_info=make_land("Forest", "G"))
    data = game.action_cast(0)
    assert "error" not in data
    evolver_perm = next(
        perm for perm in game.state.zones.battlefield if perm.name == "Shambleshark"
    )
    data = game.action_cast(0)
    assert "error" not in data
    assert evolver_perm.counters.get("+1/+1") == 1


def test_equip_attaches_equipment_in_game_loop():
    """Equip activated ability attaches an equipment to a creature host."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    host = place_on_battlefield(make_creature("Soldier", 2, 2), 0, game.state.zones)
    sword = place_on_battlefield(
        make_card("Sword", type_line="Artifact — Equipment", oracle="Equip {2}"),
        0,
        game.state.zones,
    )
    put_lands_on_battlefield(game, 2)
    data = game.action_activate(str(sword.obj_id), 0, str(host.obj_id))
    assert "error" not in data
    assert sword.attached_to == host.obj_id


def test_fabricate_creature_enters_with_counters():
    """Fabricate puts +1/+1 counters on the creature when cast."""
    welder = make_creature("Welder", 3, 3, oracle="Fabricate 2", mana_cost="{4}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 4)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=welder),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    welder_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Welder")
    assert welder_perm.counters.get("+1/+1") == 2


def test_extort_drains_when_spell_is_cast():
    """Extort drains the opponent when you cast a spell."""
    opt = make_instant("Opt", mana_cost="{U}", oracle="Draw a card.")
    extorter = make_creature("Extortionist", 2, 2, oracle="Extort")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    place_on_battlefield(extorter, 0, game.state.zones)
    put_lands_on_battlefield(game, 1, land_info=make_land("Island", "U"))
    opponent_life = game.state.players[1].life
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=opt),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    assert game.state.players[1].life == opponent_life - 1


def test_renown_marks_creature_after_unblocked_damage():
    """Renown adds +1/+1 when the creature deals combat damage to a player."""
    knight = make_creature("Knight", 2, 2, oracle="Renown 1")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    knight_perm = place_on_battlefield(knight, 0, game.state.zones, sick=False)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(knight_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert knight_perm.counters.get("+1/+1") == 1
    assert knight_perm.counters.get("renowned") == 1


def test_morph_cast_enters_face_down():
    """Morph casts a creature face down as a 2/2."""
    shifter = make_creature("Shifter", 4, 4, oracle="Morph {2}{G}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 3)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=shifter),
    ]
    data = game.action_cast(0, cast_options=cast_announce_options(cast_for_morph=True))
    assert "error" not in data
    shifter_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Shifter")
    assert shifter_perm.face_down


def test_disguise_cast_enters_face_down():
    """Disguise casts a creature face down as a 2/2."""
    spy = make_creature("Spy", 3, 3, oracle="Disguise {1}{U}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 3, land_info=make_land("Island", "U"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=spy),
    ]
    data = game.action_cast(0, cast_options=cast_announce_options(cast_for_disguise=True))
    assert "error" not in data
    spy_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Spy")
    assert spy_perm.face_down
