"""Unit tests for batch 35 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.other.afterlife import apply_afterlife_on_die, has_afterlife
from engine.abilities.keywords.other.backup import apply_backup_etb, has_backup
from engine.abilities.keywords.other.bloodthirst import apply_bloodthirst_etb, has_bloodthirst
from engine.abilities.keywords.other.daybound import apply_daybound_etb, has_daybound_card
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.ability_words.effects import ProwessEffect
from engine.abilities.keywords.other.evolve import EvolveEffect, has_evolve
from engine.abilities.keywords.other.prowess import has_prowess, has_prowess_card
from engine.core.game_object import TriggeredAbilityOnStack
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_afterlife_creates_spirit_on_death():
    """Afterlife creates Spirit tokens when the permanent dies."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Orzhov', 2, 2, oracle='Afterlife 2'),
        0,
        game.zones,
    )
    assert has_afterlife(perm)
    detail = apply_afterlife_on_die(game, perm)
    assert detail is not None
    assert 'Spirit' in detail
    spirits = [p for p in game.zones.battlefield if 'Spirit' in p.type_line]
    assert len(spirits) == 2


def test_backup_puts_counters_on_ally():
    """Backup adds +1/+1 counters to another creature you control."""
    game = fresh_game()
    ally = place_on_battlefield(make_creature('Ally', 2, 2), 0, game.zones)
    backup_creature = place_on_battlefield(
        make_creature('Backup Mage', 1, 1, oracle='Backup 2'),
        0,
        game.zones,
    )
    assert has_backup(backup_creature)
    detail = apply_backup_etb(backup_creature, game.zones.battlefield)
    assert detail is not None
    assert ally.counters.get('+1/+1') == 2


def test_bloodthirst_adds_counters_after_opponent_damaged():
    """Bloodthirst adds counters when an opponent was dealt damage this turn."""
    game = fresh_game()
    game.players[1].was_dealt_damage_this_turn = True
    perm = place_on_battlefield(
        make_creature('Thrill-Kill', 2, 2, oracle='Bloodthirst 2'),
        0,
        game.zones,
    )
    assert has_bloodthirst(perm)
    detail = apply_bloodthirst_etb(game, perm)
    assert detail is not None
    assert perm.counters.get('+1/+1') == 2


def test_daybound_enters_on_front_face():
    """Daybound permanents enter on the front face."""
    perm = place_on_battlefield(
        make_creature('Hunter', 3, 3, oracle='Daybound'),
        0,
        fresh_game().zones,
    )
    card = perm.card_info
    assert card is not None
    assert has_daybound_card(card)
    detail = apply_daybound_etb(perm)
    assert detail is not None
    assert perm.counters.get('daybound_front', 0) == 1


def test_evolve_registers_and_triggers_on_larger_creature():
    """Evolve registers on ETB and triggers when a larger creature enters."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature('Shambleshark', 1, 1, oracle='Evolve'),
        0,
        game.zones,
    )
    assert has_evolve(source)
    apply_etb_other_abilities(game, source)
    place_on_battlefield(make_creature('Ripjaw', 6, 6), 0, game.zones)
    trigger = game.stack.top
    assert isinstance(trigger, TriggeredAbilityOnStack)
    assert trigger.source_permanent_id == source.obj_id
    assert isinstance(trigger.effect, EvolveEffect)


def test_prowess_keyword_helpers():
    """Prowess is exposed on cards and permanents."""
    card = make_creature('Swiftspear', 1, 2, oracle='Prowess')
    assert has_prowess_card(card)
    perm = place_on_battlefield(card, 0, fresh_game().zones)
    assert has_prowess(perm)
    assert ProwessEffect().describe() == 'Prowess (+1/+1)'
