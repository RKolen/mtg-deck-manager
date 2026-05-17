"""Unit tests for engine/rules/combat.py."""

from engine.rules.combat import can_attack, can_block, eligible_attackers
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


def test_can_block_requires_untapped_creature_but_allows_sick_creature():
    """Summoning sickness does not prevent blocking."""
    game = fresh_game()
    blocker = place_on_battlefield(make_creature("Blocker"), 0, game.zones, sick=True)
    tapped = place_on_battlefield(make_creature("Tapped"), 0, game.zones, sick=True)
    tapped.tapped = True
    assert can_block(blocker)
    assert not can_block(tapped)


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
