"""Unit tests for engine/rules/combat.py."""

from engine.rules.combat import can_attack, can_block, eligible_attackers, legal_blocker
from engine.rules.combat import power, resolve_combat_damage, tap_attackers
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_can_attack_requires_creature_untapped_and_not_sick():
    """Only ready creatures are eligible attackers."""
    game = fresh_game()
    ready = place_on_battlefield(make_creature("Ready"), 0, game.zones, sick=False)
    sick = place_on_battlefield(make_creature("Sick"), 0, game.zones, sick=True)
    tapped = place_on_battlefield(make_creature("Tapped"), 0, game.zones, sick=False)
    tapped.tapped = True
    assert can_attack(ready)
    assert not can_attack(sick)
    assert not can_attack(tapped)


def test_defender_creature_cannot_attack():
    """Defender prevents a ready creature from attacking."""
    game = fresh_game()
    wall = place_on_battlefield(
        make_creature("Wall", 0, 4, oracle="Defender"),
        0,
        game.zones,
        sick=False,
    )
    assert not can_attack(wall)


def test_can_block_requires_untapped_creature_but_allows_sick_creature():
    """Summoning sickness does not prevent blocking."""
    game = fresh_game()
    blocker = place_on_battlefield(make_creature("Blocker"), 0, game.zones, sick=True)
    tapped = place_on_battlefield(make_creature("Tapped"), 0, game.zones, sick=True)
    tapped.tapped = True
    assert can_block(blocker)
    assert not can_block(tapped)


def test_flying_attacker_requires_flying_or_reach_blocker():
    """Ground creatures cannot block flying attackers."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature("Wind Drake", 2, 2, oracle="Flying"),
        1,
        game.zones,
    )
    ground = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.zones)
    flyer = place_on_battlefield(
        make_creature("Bird", 1, 1, oracle="Flying"),
        0,
        game.zones,
    )
    reach = place_on_battlefield(
        make_creature("Spider", 1, 4, oracle="Reach"),
        0,
        game.zones,
    )
    assert not legal_blocker(ground, attacker, game)
    assert legal_blocker(flyer, attacker, game)
    assert legal_blocker(reach, attacker, game)


def test_ground_attacker_can_be_blocked_by_ground_creature():
    """Flying/reach restrictions apply only when the attacker has flying."""
    game = fresh_game()
    attacker = place_on_battlefield(make_creature("Bear", 2, 2), 1, game.zones)
    blocker = place_on_battlefield(make_creature("Soldier", 1, 1), 0, game.zones)
    assert legal_blocker(blocker, attacker, game)


def test_power_includes_plus_and_minus_counters():
    """Combat power is printed power adjusted by +/- counters."""
    game = fresh_game()
    creature = place_on_battlefield(make_creature("Countered", 2, 2), 0, game.zones)
    creature.counters["+1/+1"] = 2
    creature.counters["-1/-1"] = 1
    assert power(creature) == 3


def test_eligible_attackers_filters_ineligible_permanents():
    """eligible_attackers returns only permanents that can currently attack."""
    game = fresh_game()
    ready = place_on_battlefield(make_creature("Ready"), 0, game.zones, sick=False)
    place_on_battlefield(make_creature("Sick"), 0, game.zones, sick=True)
    assert eligible_attackers(game.zones.permanents_of(0)) == [ready]


def test_tap_attackers_marks_each_attacker_tapped():
    """Declaring attackers taps those creatures."""
    game = fresh_game()
    attacker = place_on_battlefield(make_creature("Attacker"), 0, game.zones, sick=False)
    tap_attackers([attacker])
    assert attacker.tapped


def test_tap_attackers_leaves_vigilance_attacker_untapped():
    """Vigilance attackers do not tap when declared as attackers."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature("Sentinel", 2, 2, oracle="Vigilance"),
        0,
        game.zones,
        sick=False,
    )
    tap_attackers([attacker])
    assert not attacker.tapped


def test_vigilance_attacker_deals_damage_without_tapping():
    """Vigilance does not prevent combat damage, only attacker tapping."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature("Sentinel", 2, 2, oracle="Vigilance"),
        0,
        game.zones,
    )
    result = resolve_combat_damage(
        game,
        attacking_player_idx=0,
        defending_player_idx=1,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={},
    )
    assert result.damage_to_player == 2
    assert game.players[1].life == 18
    assert not attacker.tapped


def test_resolve_combat_damage_deals_unblocked_damage_to_defender():
    """Unblocked attackers damage the defending player."""
    game = fresh_game()
    attacker = place_on_battlefield(make_creature("Goblin", 2, 2), 0, game.zones)
    result = resolve_combat_damage(
        game,
        attacking_player_idx=0,
        defending_player_idx=1,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={},
    )
    assert result.damage_to_player == 2
    assert game.players[1].life == 18


def test_resolve_combat_damage_marks_blocker_and_attacker_damage():
    """Blocked attackers assign creature combat damage instead of player damage."""
    game = fresh_game()
    attacker = place_on_battlefield(make_creature("Attacker", 3, 3), 1, game.zones)
    blocker = place_on_battlefield(make_creature("Blocker", 1, 4), 0, game.zones)
    result = resolve_combat_damage(
        game,
        attacking_player_idx=1,
        defending_player_idx=0,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={str(blocker.obj_id): str(attacker.obj_id)},
    )
    assert result.damage_to_player == 0
    assert result.blocked_attackers == 1
    assert attacker.damage_marked == 1
    assert blocker.damage_marked == 3


def test_menace_attacker_needs_two_blockers():
    """A menace creature is not blocked by only one creature."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature("Menacer", 2, 2, oracle="Menace"),
        1,
        game.zones,
    )
    blocker = place_on_battlefield(make_creature("Blocker", 2, 2), 0, game.zones)
    result = resolve_combat_damage(
        game,
        attacking_player_idx=1,
        defending_player_idx=0,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={str(blocker.obj_id): str(attacker.obj_id)},
    )
    assert result.damage_to_player == 2
    assert result.blocked_attackers == 0
    assert game.players[0].life == 18


def test_menace_attacker_can_be_blocked_by_two_creatures():
    """Two legal blockers satisfy menace."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature("Menacer", 2, 2, oracle="Menace"),
        1,
        game.zones,
    )
    first = place_on_battlefield(make_creature("First", 2, 2), 0, game.zones)
    second = place_on_battlefield(make_creature("Second", 2, 2), 0, game.zones)
    result = resolve_combat_damage(
        game,
        attacking_player_idx=1,
        defending_player_idx=0,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={
            str(first.obj_id): str(attacker.obj_id),
            str(second.obj_id): str(attacker.obj_id),
        },
    )
    assert result.damage_to_player == 0
    assert result.blocked_attackers == 1
    assert game.players[0].life == 20
    assert first.damage_marked == 2


def test_resolve_combat_damage_ignores_invalid_blocker_assignments():
    """Missing or wrong-controller blockers do not stop combat damage."""
    game = fresh_game()
    attacker = place_on_battlefield(make_creature("Attacker", 2, 2), 1, game.zones)
    wrong_blocker = place_on_battlefield(make_creature("Wrong Side", 2, 2), 1, game.zones)
    result = resolve_combat_damage(
        game,
        attacking_player_idx=1,
        defending_player_idx=0,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={str(wrong_blocker.obj_id): str(attacker.obj_id)},
    )
    assert result.damage_to_player == 2
    assert result.blocked_attackers == 0
    assert game.players[0].life == 18


def test_resolve_combat_damage_ignores_illegal_flying_blocker():
    """Illegal ground blockers do not stop flying combat damage."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature("Wind Drake", 2, 2, oracle="Flying"),
        1,
        game.zones,
    )
    blocker = place_on_battlefield(make_creature("Bear", 2, 2), 0, game.zones)
    result = resolve_combat_damage(
        game,
        attacking_player_idx=1,
        defending_player_idx=0,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={str(blocker.obj_id): str(attacker.obj_id)},
    )
    assert result.damage_to_player == 2
    assert result.blocked_attackers == 0
    assert game.players[0].life == 18
