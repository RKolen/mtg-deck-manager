"""Unit tests for read ahead, station, and umbra armor (batch 29)."""

from __future__ import annotations

from engine.abilities.keywords.combat import can_attack
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.read_ahead import apply_read_ahead_etb, has_read_ahead
from engine.abilities.keywords.other.station import (
    apply_station,
    has_station,
    is_stationed,
)
from engine.abilities.keywords.other.umbra_armor import (
    has_umbra_armor,
    try_umbra_armor_replacement,
)
from tests.conftest import _CardStats, fresh_game, make_card, make_creature, place_on_battlefield


def test_read_ahead_puts_lore_on_saga():
    """Read ahead Sagas enter with extra lore counters."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_card(
            name='Story',
            type_line='Enchantment — Saga',
            oracle='Read ahead 2\n(I) Scry 1.',
            mana_cost='{2}{U}',
            stats=_CardStats(cmc=3.0, pt='0/0'),
        ),
        0,
        game.zones,
    )
    assert has_read_ahead(perm)
    detail = apply_read_ahead_etb(perm)
    assert detail is not None
    assert perm.counters.get('lore', 0) == 3


def test_station_animates_spacecraft():
    """Stationed spacecraft can attack."""
    game = fresh_game()
    ship = place_on_battlefield(
        make_card(
            name='Probe',
            type_line='Artifact — Spacecraft',
            oracle='Station 2\nFlying',
            mana_cost='{3}',
            stats=_CardStats(cmc=3.0, pt='0/0'),
        ),
        0,
        game.zones,
    )
    crewer = place_on_battlefield(make_creature('Pilot', 3, 3), 0, game.zones)
    assert has_station(ship)
    apply_station(game, ship, [str(crewer.obj_id)])
    ship.sick = False
    assert is_stationed(ship)
    assert can_attack(ship)


def test_umbra_armor_saves_enchanted_creature():
    """Umbra armor exiles itself instead of the creature dying."""
    game = fresh_game()
    creature = place_on_battlefield(make_creature('Bearer', 2, 2), 0, game.zones)
    aura = place_on_battlefield(
        make_card(
            name='Shield',
            type_line='Enchantment — Aura',
            oracle='Umbra armor\nEnchant creature',
            mana_cost='{W}',
            stats=_CardStats(cmc=1.0, pt='0/0'),
        ),
        0,
        game.zones,
    )
    aura.attached_to = creature.obj_id
    creature.damage_marked = 5
    assert has_umbra_armor(aura)
    assert try_umbra_armor_replacement(game, creature)
    assert creature.damage_marked == 0
    assert aura not in game.zones.battlefield


def test_read_ahead_etb_hook_runs_from_registry():
    """Read ahead is wired through apply_etb_other_abilities."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_card(
            name='Tale',
            type_line='Enchantment — Saga',
            oracle='Read ahead 1',
            mana_cost='{1}{G}',
            stats=_CardStats(cmc=2.0, pt='0/0'),
        ),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, perm)
    assert any('read ahead' in line for line in details)
