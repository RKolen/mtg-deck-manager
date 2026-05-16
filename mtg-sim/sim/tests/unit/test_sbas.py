"""Unit tests for engine/rules/state_based.py (CR 704 state-based actions)."""

from engine.core.game_object import TokenObject
from engine.rules.state_based import check_sbas
from tests.conftest import (
    fresh_game,
    make_card,
    make_creature,
    place_on_battlefield,
)


# ---------------------------------------------------------------------------
# CR 704.5a — player life <= 0
# ---------------------------------------------------------------------------

def test_player_zero_life_loses():
    """A player at exactly 0 life triggers the life-loss SBA and loses the game."""
    game = fresh_game(player_life=0)
    events = check_sbas(game)
    assert any(e.rule == "704.5a" for e in events)
    assert game.winner == 1


def test_player_negative_life_loses():
    """Negative life also triggers the life-loss SBA."""
    game = fresh_game(player_life=-3)
    check_sbas(game)
    assert game.winner == 1


def test_player_one_life_survives():
    """A player at 1 life does not trigger any life-loss SBA."""
    game = fresh_game(player_life=1)
    events = check_sbas(game)
    assert not any(e.rule == "704.5a" for e in events)
    assert game.winner is None


def test_opponent_zero_life_loses():
    """Opponent at 0 life sets winner to the player (index 0)."""
    game = fresh_game(opponent_life=0)
    check_sbas(game)
    assert game.winner == 0


def test_both_zero_life_winner_set():
    """When both players are at 0 life the SBA checker still sets a winner."""
    game = fresh_game(player_life=0, opponent_life=0)
    check_sbas(game)
    assert game.winner is not None


# ---------------------------------------------------------------------------
# CR 704.5c — poison counters >= 10
# ---------------------------------------------------------------------------

def test_ten_poison_loses():
    """A player with 10 poison counters triggers the poison SBA and loses."""
    game = fresh_game()
    game.players[0].poison = 10
    events = check_sbas(game)
    assert any(e.rule == "704.5c" for e in events)
    assert game.winner == 1


def test_nine_poison_survives():
    """Nine poison counters do not trigger the poison SBA."""
    game = fresh_game()
    game.players[0].poison = 9
    events = check_sbas(game)
    assert not any(e.rule == "704.5c" for e in events)


# ---------------------------------------------------------------------------
# CR 704.5f — creature toughness <= 0
# ---------------------------------------------------------------------------

def test_zero_toughness_creature_dies():
    """A creature printed at 0 toughness immediately triggers the toughness SBA."""
    game = fresh_game()
    creature = place_on_battlefield(make_creature("Test", 2, 0), 0, game.zones)
    events = check_sbas(game)
    assert any(e.rule == "704.5f" for e in events)
    assert creature not in game.zones.battlefield


def test_minus_one_minus_one_counter_kills_one_one():
    """A -1/-1 counter on a 1/1 reduces toughness to 0, triggering CR 704.5f."""
    game = fresh_game()
    creature = place_on_battlefield(make_creature("1/1", 1, 1), 0, game.zones)
    creature.counters["-1/-1"] = 1
    events = check_sbas(game)
    assert any(e.rule == "704.5f" for e in events)
    assert creature not in game.zones.battlefield


def test_one_toughness_creature_survives():
    """A 1/1 with no damage or counters does not trigger any creature SBA."""
    game = fresh_game()
    creature = place_on_battlefield(make_creature("1/1", 1, 1), 0, game.zones)
    events = check_sbas(game)
    assert not any(e.rule in ("704.5f", "704.5g") for e in events)
    assert creature in game.zones.battlefield


# ---------------------------------------------------------------------------
# CR 704.5g — creature with lethal damage
# ---------------------------------------------------------------------------

def test_lethal_damage_creature_dies():
    """A creature with damage equal to its toughness triggers the lethal-damage SBA."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.zones)
    bear.damage_marked = 2
    events = check_sbas(game)
    assert any(e.rule == "704.5g" for e in events)
    assert bear not in game.zones.battlefield


def test_lethal_damage_goes_to_graveyard():
    """A creature that dies from lethal damage is placed in its owner's graveyard."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.zones)
    bear.damage_marked = 3
    check_sbas(game)
    assert len(game.zones.player_zones[0].graveyard) == 1


def test_one_less_than_lethal_survives():
    """Damage one below toughness does not trigger CR 704.5g."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.zones)
    bear.damage_marked = 1
    events = check_sbas(game)
    assert not any(e.rule == "704.5g" for e in events)
    assert bear in game.zones.battlefield


def test_indestructible_ignores_lethal_damage():
    """An indestructible creature is not destroyed by lethal damage (CR 702.12)."""
    game = fresh_game()
    god = place_on_battlefield(
        make_creature("God", 5, 5, oracle="Indestructible."), 0, game.zones
    )
    god.damage_marked = 5
    events = check_sbas(game)
    assert not any(e.rule == "704.5g" for e in events)
    assert god in game.zones.battlefield


# ---------------------------------------------------------------------------
# CR 704.5i — planeswalker at 0 loyalty
# ---------------------------------------------------------------------------

def test_planeswalker_zero_loyalty_dies():
    """A planeswalker with 0 loyalty counters triggers CR 704.5i."""
    game = fresh_game()
    pw_info = make_card("Liliana", type_line="Legendary Planeswalker — Liliana")
    pw = place_on_battlefield(pw_info, 0, game.zones)
    pw.counters["loyalty"] = 0
    events = check_sbas(game)
    assert any(e.rule == "704.5i" for e in events)
    assert pw not in game.zones.battlefield


def test_planeswalker_one_loyalty_survives():
    """A planeswalker at 1 loyalty does not trigger CR 704.5i."""
    game = fresh_game()
    pw_info = make_card("Liliana", type_line="Legendary Planeswalker — Liliana")
    pw = place_on_battlefield(pw_info, 0, game.zones)
    pw.counters["loyalty"] = 1
    events = check_sbas(game)
    assert not any(e.rule == "704.5i" for e in events)


# ---------------------------------------------------------------------------
# CR 704.5j — legend rule
# ---------------------------------------------------------------------------

def test_legend_rule_removes_newer_copy():
    """Two legendary permanents with the same name: the newer one is removed."""
    game = fresh_game()
    info = make_card("Snapcaster Mage", type_line="Legendary Creature — Human Wizard")
    older = place_on_battlefield(info, 0, game.zones)
    newer = place_on_battlefield(info, 0, game.zones)
    assert older.timestamp < newer.timestamp
    events = check_sbas(game)
    assert any(e.rule == "704.5j" for e in events)
    assert older in game.zones.battlefield
    assert newer not in game.zones.battlefield


def test_legend_rule_different_names_both_survive():
    """Two different legendary creatures do not trigger the legend rule."""
    game = fresh_game()
    place_on_battlefield(make_card("Urza", type_line="Legendary Creature — Human"), 0, game.zones)
    place_on_battlefield(make_card("Mishra", type_line="Legendary Creature — Human"), 0, game.zones)
    events = check_sbas(game)
    assert not any(e.rule == "704.5j" for e in events)


def test_legend_rule_different_controllers_both_survive():
    """Same legendary permanent controlled by different players: both survive."""
    game = fresh_game()
    info = make_card("Snapcaster Mage", type_line="Legendary Creature — Human Wizard")
    place_on_battlefield(info, 0, game.zones)
    place_on_battlefield(info, 1, game.zones)
    events = check_sbas(game)
    assert not any(e.rule == "704.5j" for e in events)


# ---------------------------------------------------------------------------
# CR 704.5m — aura not attached to legal permanent
# ---------------------------------------------------------------------------

def test_aura_detaches_when_host_dies():
    """An aura whose host left the battlefield goes to the graveyard (CR 704.5m)."""
    game = fresh_game()
    host = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.zones)
    aura_info = make_card("Pacifism", type_line="Enchantment — Aura", oracle="Enchant creature.")
    aura = place_on_battlefield(aura_info, 0, game.zones)
    aura.attached_to = host.obj_id
    game.zones.battlefield.remove(host)
    events = check_sbas(game)
    assert any(e.rule == "704.5m" for e in events)
    assert aura not in game.zones.battlefield


def test_aura_with_valid_host_survives():
    """An aura attached to a living host does not trigger CR 704.5m."""
    game = fresh_game()
    host = place_on_battlefield(make_creature(), 0, game.zones)
    aura_info = make_card("Pacifism", type_line="Enchantment — Aura")
    aura = place_on_battlefield(aura_info, 0, game.zones)
    aura.attached_to = host.obj_id
    events = check_sbas(game)
    assert not any(e.rule == "704.5m" for e in events)


# ---------------------------------------------------------------------------
# CR 704.5n — equipment falls off non-creature
# ---------------------------------------------------------------------------

def test_equipment_falls_off_non_creature():
    """Equipment attached to a non-creature permanent detaches (CR 704.5n)."""
    game = fresh_game()
    rock = place_on_battlefield(make_card("Mox", type_line="Artifact"), 0, game.zones)
    equip_info = make_card("Sword", type_line="Artifact — Equipment")
    equip = place_on_battlefield(equip_info, 0, game.zones)
    equip.attached_to = rock.obj_id
    events = check_sbas(game)
    assert any(e.rule == "704.5n" for e in events)
    assert equip.attached_to is None


def test_equipment_stays_on_creature():
    """Equipment attached to a creature does not trigger CR 704.5n."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature(), 0, game.zones)
    equip_info = make_card("Sword", type_line="Artifact — Equipment")
    equip = place_on_battlefield(equip_info, 0, game.zones)
    equip.attached_to = bear.obj_id
    events = check_sbas(game)
    assert not any(e.rule == "704.5n" for e in events)
    assert equip.attached_to == bear.obj_id


# ---------------------------------------------------------------------------
# CR 704.5d — token not on battlefield ceases to exist
# ---------------------------------------------------------------------------

def test_token_in_hand_ceases_to_exist():
    """A token that somehow ends up in a player's hand ceases to exist (CR 704.5d)."""
    game = fresh_game()
    token = TokenObject(
        controller_idx=0,
        owner_idx=0,
        name="Goblin Token",
        type_line="Creature — Goblin",
        power="1",
        toughness="1",
    )
    game.zones.player_zones[0].hand.append(token)  # type: ignore[arg-type]
    events = check_sbas(game)
    assert any(e.rule == "704.5d" for e in events)
    assert token not in game.zones.player_zones[0].hand


# ---------------------------------------------------------------------------
# SBA chain — one SBA triggers another in the same pass
# ---------------------------------------------------------------------------

def test_sbas_repeat_until_stable():
    """Dying creature leaves aura orphaned; second SBA pass removes the aura too."""
    game = fresh_game()
    bear = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.zones)
    aura_info = make_card("Holy Strength", type_line="Enchantment — Aura")
    aura = place_on_battlefield(aura_info, 0, game.zones)
    aura.attached_to = bear.obj_id
    bear.damage_marked = 2
    check_sbas(game)
    assert bear not in game.zones.battlefield
    assert aura not in game.zones.battlefield
