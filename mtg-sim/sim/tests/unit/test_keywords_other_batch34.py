"""Unit tests for batch 34 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.handlers import apply_combat_damage_to_creature
from engine.abilities.keywords.other.absorb import has_absorb
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.exploit import apply_exploit_etb, has_exploit
from engine.abilities.keywords.other.living_weapon import apply_living_weapon, has_living_weapon
from engine.abilities.keywords.other.modular import apply_modular_etb, has_modular
from engine.abilities.keywords.other.nightbound import (
    apply_nightbound_etb,
    has_nightbound,
    resolve_nightbound_upkeep,
)
from engine.abilities.keywords.other.riot import has_riot
from tests.conftest import fresh_game, make_card, make_creature, place_on_battlefield


def test_exploit_sacrifices_on_etb():
    """Exploit sacrifices another creature when this permanent enters."""
    game = fresh_game()
    exploiter = make_creature('Marchesa', 3, 3, oracle='Exploit')
    fodder = place_on_battlefield(make_creature('Fodder', 1, 1), 0, game.zones)
    host = place_on_battlefield(exploiter, 0, game.zones)
    assert has_exploit(host)
    detail = apply_exploit_etb(game, host)
    assert detail is not None
    assert 'sacrificed' in detail
    assert fodder in game.zones.player_zones[0].graveyard
    details = apply_etb_other_abilities(game, host)
    assert any('exploit' in item for item in details)


def test_riot_puts_counter_on_etb():
    """Riot adds a +1/+1 counter when the creature enters."""
    game = fresh_game()
    perm = place_on_battlefield(make_creature('Rioter', 2, 2, oracle='Riot'), 0, game.zones)
    assert has_riot(perm)
    details = apply_etb_other_abilities(game, perm)
    assert any('riot' in detail for detail in details)
    assert perm.counters.get('+1/+1') == 1


def test_living_weapon_creates_germ():
    """Living weapon creates a Germ token and attaches equipment."""
    game = fresh_game()
    sword = place_on_battlefield(
        make_card(
            'Skullclamp',
            type_line='Artifact — Equipment',
            oracle='Living weapon',
        ),
        0,
        game.zones,
    )
    assert has_living_weapon(sword.oracle_text or '')
    detail = apply_living_weapon(game.zones, sword)
    assert detail is not None
    assert sword.attached_to is not None


def test_modular_enters_with_counters():
    """Modular ETB puts +1/+1 counters on the permanent."""
    game = fresh_game()
    worker = place_on_battlefield(
        make_creature('Modular Golem', 0, 0, oracle='Modular 3'),
        0,
        game.zones,
    )
    assert has_modular(worker)
    assert apply_modular_etb(worker) is not None
    assert worker.counters.get('+1/+1') == 3


def test_nightbound_enters_back_and_toggles():
    """Nightbound permanents enter on the back face and toggle at upkeep."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Werewolf', 3, 3, oracle='Nightbound'),
        0,
        game.zones,
    )
    assert has_nightbound(perm)
    detail = apply_nightbound_etb(perm)
    assert detail is not None
    assert perm.counters.get('daybound_front', 1) == 0
    details = resolve_nightbound_upkeep(game, 0)
    assert details
    assert perm.counters.get('daybound_front', 0) == 1


def test_absorb_reduces_incoming_combat_damage():
    """Absorb prevents combat damage to a permanent."""
    game = fresh_game()
    blocker = place_on_battlefield(
        make_creature('Loxodon', 2, 3, oracle='Absorb 2'),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(make_creature('Raider', 4, 4), 1, game.zones)
    assert has_absorb(blocker)
    apply_combat_damage_to_creature(blocker, attacker, 3)
    assert blocker.damage_marked == 1
