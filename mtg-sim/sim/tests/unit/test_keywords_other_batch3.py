"""Unit tests for ability_other batch 3: afterlife, backup, annihilator, blitz."""

from __future__ import annotations

from engine.abilities.keywords.other.afterlife import apply_afterlife_on_die
from engine.abilities.keywords.other.annihilator import apply_annihilator_on_attack
from engine.abilities.keywords.other.blitz import sacrifice_blitz_creatures
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from tests.conftest import fresh_game, make_creature, make_land, place_on_battlefield


def test_afterlife_creates_spirit_on_death():
    """Afterlife creates Spirit tokens when the permanent dies."""
    game = fresh_game()
    spirit_host = place_on_battlefield(
        make_creature('Orzhov', 2, 2, oracle='Afterlife 1'),
        0,
        game.zones,
    )
    detail = apply_afterlife_on_die(game, spirit_host)
    assert detail
    spirits = [
        p for p in game.zones.battlefield
        if 'Spirit' in p.type_line and p.controller_idx == 0
    ]
    assert len(spirits) == 1


def test_backup_puts_counters_on_ally():
    """Backup puts +1/+1 on another creature you control."""
    game = fresh_game()
    ally = place_on_battlefield(make_creature('Ally', 1, 1), 0, game.zones)
    backup_creature = place_on_battlefield(
        make_creature('Backup Host', 2, 2, oracle='Backup 2'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, backup_creature)
    assert any('backup' in detail for detail in details)
    assert ally.counters.get('+1/+1') == 2


def test_annihilator_destroys_defender_permanents():
    """Annihilator destroys defending permanents on attack."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Ulamog', 10, 10, oracle='Annihilator 2'),
        0,
        game.zones,
        sick=False,
    )
    place_on_battlefield(make_land('Mountain'), 1, game.zones)
    place_on_battlefield(make_land('Island'), 1, game.zones)
    detail = apply_annihilator_on_attack(game, attacker)
    assert detail
    assert len([p for p in game.zones.battlefield if p.controller_idx == 1]) == 0


def test_blitz_creature_sacrificed_at_end_of_turn():
    """Blitzed creatures are sacrificed at end of turn."""
    game = fresh_game()
    blitzer = place_on_battlefield(
        make_creature('Blitzer', 2, 2, oracle='Blitz {1}{R}'),
        0,
        game.zones,
    )
    apply_etb_other_abilities(game, blitzer)
    assert blitzer.counters.get('blitz') == 1
    details = sacrifice_blitz_creatures(game, 0)
    assert details
    assert len(game.zones.battlefield) == 0
