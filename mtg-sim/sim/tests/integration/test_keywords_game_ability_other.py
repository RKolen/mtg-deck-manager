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
    resolve_stack_fully,
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
_LIVING_WEAPON_ORACLE = (
    "Living weapon (When this Equipment enters, create a 0/0 black Germ "
    "creature token, then attach this to it.)\n"
    "Equipped creature gets +4/+4."
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


def test_bloodthirst_puts_counters_after_opponent_was_damaged():
    """Bloodthirst adds +1/+1 counters when the opponent was damaged this turn."""
    shock = make_instant("Shock", mana_cost="{R}", oracle="Shock deals 2 damage to any target.")
    gore = make_creature("Gore-House", 2, 2, oracle="Bloodthirst 2", mana_cost="{2}{R}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 4, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=shock),
        CardObject(controller_idx=0, owner_idx=0, card_info=gore),
    ]
    data = game.action_cast(0, target_player=1)
    assert "error" not in data
    data = game.action_cast(0)
    assert "error" not in data
    gore_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Gore-House")
    assert gore_perm.counters.get("+1/+1") == 2


def test_riot_creature_enters_with_counter_in_game_loop():
    """Riot puts a +1/+1 counter on the creature when it enters."""
    goblin = make_creature("Goblin", 1, 1, oracle="Riot", mana_cost="{R}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=goblin),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    goblin_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Goblin")
    assert goblin_perm.counters.get("+1/+1") == 1


def test_modular_moves_counters_when_creature_dies():
    """Modular transfers +1/+1 counters to another artifact when the donor dies."""
    worker = make_creature("Arcbound Worker", 0, 0, oracle="Modular 2", mana_cost="{4}")
    recipient = make_card(
        "Golem",
        type_line="Artifact Creature — Golem",
        stats=_CardStats(cmc=2.0, pt="1/1"),
    )
    shock = make_instant("Shock", mana_cost="{R}", oracle="Shock deals 2 damage to any target.")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    place_on_battlefield(recipient, 0, game.state.zones)
    put_lands_on_battlefield(game, 5)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=worker),
        CardObject(controller_idx=0, owner_idx=0, card_info=shock),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    worker_perm = next(
        perm for perm in game.state.zones.battlefield if perm.name == "Arcbound Worker"
    )
    recipient_perm = next(
        perm for perm in game.state.zones.battlefield if perm.name == "Golem"
    )
    assert worker_perm.counters.get("+1/+1") == 2
    data = game.action_cast(0, target_uid=str(worker_perm.obj_id))
    assert "error" not in data
    assert worker_perm not in game.state.zones.battlefield
    assert recipient_perm.counters.get("+1/+1") == 2


def test_living_weapon_cast_creates_germ_host():
    """Casting living weapon equipment creates a Germ token and attaches."""
    batterskull = make_card(
        "Batterskull",
        type_line="Artifact — Equipment",
        oracle=_LIVING_WEAPON_ORACLE,
        mana_cost="{5}",
        stats=_CardStats(cmc=5.0, pt="0/0"),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 5)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=batterskull),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    sword = next(perm for perm in game.state.zones.battlefield if perm.name == "Batterskull")
    assert sword.attached_to is not None
    host = game.state.zones.find_permanent(sword.attached_to)
    assert host is not None
    assert "Germ" in host.type_line


def test_devour_sacrifices_creatures_on_cast():
    """Devour sacrifices other creatures when the host enters from a cast."""
    dragon = make_creature("Dragon", 4, 4, oracle="Devour 2", mana_cost="{4}{R}{R}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    place_on_battlefield(make_creature("Food", 1, 1), 0, game.state.zones)
    place_on_battlefield(make_creature("Fodder", 1, 1), 0, game.state.zones)
    put_lands_on_battlefield(game, 6, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=dragon),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    dragon_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Dragon")
    assert dragon_perm.counters.get("+1/+1") == 2
    assert len(game.state.zones.player_zones[0].graveyard) == 2


def test_mentor_buffs_smaller_attacker_in_combat():
    """Mentor puts +1/+1 on a weaker attacking creature during combat."""
    mentor = make_creature("Mentor", 4, 4, oracle="Mentor")
    rookie = make_creature("Rookie", 2, 2)
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    mentor_perm = place_on_battlefield(mentor, 0, game.state.zones, sick=False)
    rookie_perm = place_on_battlefield(rookie, 0, game.state.zones, sick=False)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(mentor_perm.obj_id))
    game.action_toggle_attacker(str(rookie_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert rookie_perm.counters.get("+1/+1") == 1


def test_exalted_solo_attack_adds_counter():
    """Exalted grants +1/+1 when this creature attacks alone."""
    knight = make_creature("Knight", 2, 2, oracle="Exalted")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    knight_perm = place_on_battlefield(knight, 0, game.state.zones, sick=False)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(knight_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert knight_perm.counters.get("+1/+1") == 1


def test_annihilator_destroys_defender_permanents_on_attack():
    """Annihilator destroys defending permanents when the creature attacks."""
    ulamog = make_creature("Ulamog", 10, 10, oracle="Annihilator 2")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    ulamog_perm = place_on_battlefield(ulamog, 0, game.state.zones, sick=False)
    place_on_battlefield(make_land("Mountain"), 1, game.state.zones)
    place_on_battlefield(make_land("Island"), 1, game.state.zones)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(ulamog_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert len([perm for perm in game.state.zones.battlefield if perm.controller_idx == 1]) == 0


def test_backup_puts_counters_on_ally_in_game_loop():
    """Backup puts +1/+1 on another creature you control when the host enters."""
    ally = make_creature("Ally", 1, 1)
    backup_host = make_creature("Backup Host", 2, 2, oracle="Backup 2", mana_cost="{2}{G}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    ally_perm = place_on_battlefield(ally, 0, game.state.zones)
    put_lands_on_battlefield(game, 3, land_info=make_land("Forest", "G"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=backup_host),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    assert ally_perm.counters.get("+1/+1") == 2


def test_dash_creature_returns_to_hand_at_end_of_turn():
    """Dashed creatures return to hand when the turn ends."""
    sprinter = make_card(
        "Sprinter",
        type_line="Creature — Human Warrior",
        oracle="Dash {1}{R}\nHaste",
        mana_cost="{1}{R}",
        stats=_CardStats(cmc=3.0, pt="2/1"),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 2, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=sprinter),
    ]
    data = game.action_cast(0, cast_options=cast_announce_options(cast_for_dash=True))
    assert "error" not in data
    assert any(perm.name == "Sprinter" for perm in game.state.zones.battlefield)
    data = game.action_end_turn()
    assert "error" not in data
    assert any(
        isinstance(card, CardObject)
        and card.card_info is not None
        and card.card_info.name == "Sprinter"
        for card in game.state.zones.player_zones[0].hand
    )
    assert not any(perm.name == "Sprinter" for perm in game.state.zones.battlefield)


def test_blitz_creature_sacrificed_at_end_of_turn():
    """Blitzed creatures are sacrificed when the turn ends."""
    blitzer = make_card(
        "Blitzer",
        type_line="Creature — Human Warrior",
        oracle="Blitz {1}{R}",
        mana_cost="{1}{R}",
        stats=_CardStats(cmc=2.0, pt="2/1"),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 2, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=blitzer),
    ]
    data = game.action_cast(0, cast_options=cast_announce_options(cast_for_blitz=True))
    assert "error" not in data
    assert any(perm.name == "Blitzer" for perm in game.state.zones.battlefield)
    data = game.action_end_turn()
    assert "error" not in data
    assert not any(perm.name == "Blitzer" for perm in game.state.zones.battlefield)
    assert any(
        isinstance(card, CardObject)
        and card.card_info is not None
        and card.card_info.name == "Blitzer"
        for card in game.state.zones.player_zones[0].graveyard
    )


def test_graft_moves_counter_from_donor_on_cast():
    """Graft moves a +1/+1 counter from another creature when the host enters."""
    donor = make_creature("Donor", 2, 2)
    graft_host = make_creature("Grafted", 1, 1, oracle="Graft", mana_cost="{G}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    donor_perm = place_on_battlefield(donor, 0, game.state.zones)
    donor_perm.counters["+1/+1"] = 2
    put_lands_on_battlefield(game, 1, land_info=make_land("Forest", "G"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=graft_host),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    graft_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Grafted")
    assert graft_perm.counters.get("+1/+1") == 1
    assert donor_perm.counters.get("+1/+1") == 1


def test_training_puts_counter_when_stronger_ally_attacks():
    """Training adds +1/+1 when a creature with greater power attacks with this."""
    trainee = make_creature("Trainee", 2, 2, oracle="Training")
    veteran = make_creature("Veteran", 4, 4)
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    trainee_perm = place_on_battlefield(trainee, 0, game.state.zones, sick=False)
    veteran_perm = place_on_battlefield(veteran, 0, game.state.zones, sick=False)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(trainee_perm.obj_id))
    game.action_toggle_attacker(str(veteran_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert trainee_perm.counters.get("+1/+1") == 1


def test_afflict_drains_defender_on_attack():
    """Afflict makes the defending player lose 1 life when this creature attacks."""
    afflictor = make_creature("Afflictor", 2, 2, oracle="Afflict")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    afflictor_perm = place_on_battlefield(afflictor, 0, game.state.zones, sick=False)
    game.action_go_to_attack()
    game.action_toggle_attacker(str(afflictor_perm.obj_id))
    data = game.action_confirm_attack()
    assert "error" not in data
    assert game.state.players[1].life == 17
    assert any(
        entry.action == "afflict" or "afflict" in entry.detail.lower()
        for entry in game.state.log
    )


def test_cipher_triggers_when_instant_cast_in_game_loop():
    """Cipher puts a trigger on the stack when you cast an instant or sorcery."""
    host = make_creature("Cipher Host", 1, 1, oracle="Cipher — Draw a card.", mana_cost="{G}")
    opt = make_instant("Opt", mana_cost="{U}", oracle="Draw a card.")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 1, land_info=make_land("Forest", "G"))
    put_lands_on_battlefield(game, 1, land_info=make_land("Island", "U"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=host),
        CardObject(controller_idx=0, owner_idx=0, card_info=opt),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    data = game.action_cast(0)
    assert "error" not in data
    resolve_stack_fully(game)
    assert any("cipher" in entry.detail.lower() for entry in game.state.log)


def test_undying_creature_survives_destruction_in_game_loop():
    """Undying returns a creature with a +1/+1 counter when it would die."""
    undying = make_creature("Young Wolf", 1, 1, oracle="Undying")
    shock = make_instant("Shock", mana_cost="{R}", oracle="Shock deals 2 damage to any target.")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    wolf_perm = place_on_battlefield(undying, 0, game.state.zones)
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=shock),
    ]
    data = game.action_cast(0, target_uid=str(wolf_perm.obj_id))
    assert "error" not in data
    assert wolf_perm in game.state.zones.battlefield
    assert wolf_perm.counters.get("+1/+1") == 1


def test_persist_creature_survives_with_minus_counter_in_game_loop():
    """Persist returns a creature with a -1/-1 counter when it would die."""
    persister = make_creature("Safehold", 2, 2, oracle="Persist")
    shock = make_instant("Shock", mana_cost="{R}", oracle="Shock deals 2 damage to any target.")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    safe_perm = place_on_battlefield(persister, 0, game.state.zones)
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=shock),
    ]
    data = game.action_cast(0, target_uid=str(safe_perm.obj_id))
    assert "error" not in data
    assert safe_perm in game.state.zones.battlefield
    assert safe_perm.counters.get("-1/-1") == 1


def test_ascend_grants_citys_blessing_at_ten_permanents():
    """Ascend grants City's Blessing when you control ten permanents on ETB."""
    ascendant = make_creature("Ascendant", 1, 1, oracle="Ascend", mana_cost="{W}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    for idx in range(9):
        place_on_battlefield(make_creature(f"Permanent{idx}", 1, 1), 0, game.state.zones)
    put_lands_on_battlefield(game, 1, land_info=make_land("Plains", "W"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=ascendant),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    assert game.state.players[0].ascended


def test_unleash_creature_enters_with_counter_in_game_loop():
    """Unleash adds a +1/+1 counter and marks the creature unable to block."""
    wild = make_creature("Wild", 2, 2, oracle="Unleash", mana_cost="{R}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 1, land_info=make_land("Mountain", "R"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=wild),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    wild_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Wild")
    assert wild_perm.counters.get("+1/+1") == 1
    assert wild_perm.counters.get("unleash_no_block") == 1


def test_fabricate_servos_enters_when_oracle_requests_artifact_token():
    """Fabricate creates Servo tokens when the oracle text requests artifact tokens."""
    welder = make_creature(
        "Welder",
        3,
        3,
        oracle="Fabricate 1. Create a colorless artifact token.",
        mana_cost="{4}",
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 4)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=welder),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    servos = [perm for perm in game.state.zones.battlefield if perm.name == "Servo"]
    assert len(servos) == 1


def test_prowl_marks_unblockable_when_graveyard_matches_on_cast():
    """Prowl marks the creature unblockable when a matching creature is in the graveyard."""
    ally = make_card("Ally", type_line="Creature — Human Warrior", stats=_CardStats(pt="1/1"))
    ninja = make_card(
        "Ninja",
        type_line="Creature — Human Ninja",
        oracle="Prowl {1}{B}",
        mana_cost="{1}{B}",
        stats=_CardStats(cmc=2.0, pt="2/2"),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].graveyard = [
        CardObject(controller_idx=0, owner_idx=0, card_info=ally),
    ]
    put_lands_on_battlefield(game, 2, land_info=make_land("Swamp", "B"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=ninja),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    ninja_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Ninja")
    assert ninja_perm.counters.get("prowl_unblocked") == 1


def test_decayed_creature_sacrificed_at_end_of_turn():
    """Decayed creatures are sacrificed when the turn ends."""
    walker = make_creature("Walker", 2, 2, oracle="Decayed", mana_cost="{B}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 1, land_info=make_land("Swamp", "B"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=walker),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    walker_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Walker")
    assert walker_perm.counters.get("decayed") == 1
    data = game.action_end_turn()
    assert "error" not in data
    assert not any(perm.name == "Walker" for perm in game.state.zones.battlefield)


def test_encore_from_graveyard_creates_token_copy():
    """Encore exiles a graveyard creature and creates an attacking token copy."""
    siege = make_creature("Siege", 3, 3, oracle="Encore {2}{B}", mana_cost="{2}{B}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 3, land_info=make_land("Swamp", "B"))
    game.state.zones.player_zones[0].graveyard = [
        CardObject(controller_idx=0, owner_idx=0, card_info=siege),
    ]
    data = game.action_encore(0)
    assert "error" not in data
    assert any(perm.name == "Siege" for perm in game.state.zones.battlefield)
    assert any(
        isinstance(card, CardObject)
        and card.card_info is not None
        and card.card_info.name == "Siege"
        for card in game.state.zones.player_zones[0].exile
    )


def test_soulbond_pairs_creatures_on_second_cast():
    """Soulbond pairs two creatures when the second one enters."""
    first = make_creature("First", 2, 2, oracle="Soulbond", mana_cost="{W}")
    second = make_creature("Second", 2, 2, oracle="Soulbond", mana_cost="{W}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 2, land_info=make_land("Plains", "W"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=first),
        CardObject(controller_idx=0, owner_idx=0, card_info=second),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    data = game.action_cast(0)
    assert "error" not in data
    first_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "First")
    second_perm = next(perm for perm in game.state.zones.battlefield if perm.name == "Second")
    assert first_perm.counters.get("soulbond") == second_perm.obj_id
    assert second_perm.counters.get("soulbond") == first_perm.obj_id


def test_offspring_creates_token_on_cast():
    """Offspring creates a token copy when the creature enters from a cast."""
    parent = make_creature("Parent", 2, 3, oracle="Offspring {2}", mana_cost="{2}{G}")
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 3, land_info=make_land("Forest", "G"))
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=parent),
    ]
    data = game.action_cast(0)
    assert "error" not in data
    tokens = [perm for perm in game.state.zones.battlefield if "Token" in perm.name]
    assert len(tokens) == 1
    assert any(perm.name == "Parent" for perm in game.state.zones.battlefield)
