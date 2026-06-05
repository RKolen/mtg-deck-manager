"""Unit tests for ability_other batch: extort, evolve, modular, bloodthirst."""

from __future__ import annotations

from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.extort import apply_extort_on_spell_cast
from engine.abilities.keywords.other.register import register_permanent_other_keywords
from engine.core.game_object import CardObject, TriggeredAbilityOnStack
from engine.core.zones import Zone
from tests.conftest import _CardStats, fresh_game, make_card, make_creature, place_on_battlefield


def test_extort_drains_on_spell_cast():
    """Extort drains life when the controller casts a spell."""
    game = fresh_game()
    place_on_battlefield(
        make_creature('Extortionist', 1, 1, oracle='Extort'),
        0,
        game.zones,
    )
    apply_extort_on_spell_cast(game, 0)
    assert game.players[1].life == 19
    assert game.players[0].life == 21


def test_bloodthirst_puts_counters_when_opponent_was_damaged():
    """Bloodthirst adds counters on ETB after opponent took damage."""
    game = fresh_game()
    game.players[1].was_dealt_damage_this_turn = True
    perm = place_on_battlefield(
        make_creature('Gore-House', 2, 2, oracle='Bloodthirst 2'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, perm)
    assert any('bloodthirst' in detail for detail in details)
    assert perm.counters.get('+1/+1') == 2


def test_modular_transfers_counters_on_death():
    """Modular moves +1/+1 counters to another artifact when the source dies."""
    game = fresh_game()
    donor = place_on_battlefield(
        make_creature('Arcbound Worker', 0, 0, oracle='Modular 2'),
        0,
        game.zones,
    )
    donor.counters['+1/+1'] = 2
    recipient = place_on_battlefield(
        make_card('Recipient', type_line='Artifact Creature — Golem', stats=_CardStats(pt='1/1')),
        0,
        game.zones,
    )
    game.zones.leave_battlefield(donor, Zone.GRAVEYARD, 'test', game)
    assert recipient.counters.get('+1/+1') == 2


def test_evolve_trigger_when_larger_creature_enters():
    """Evolve puts a trigger on the stack when a bigger creature enters."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature('Evolver', 1, 1, oracle='Evolve'),
        0,
        game.zones,
    )
    register_permanent_other_keywords(source, game.trigger_registry)
    bigger = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature('Big', 5, 5),
    )
    game.zones.enter_battlefield(bigger, 0, 'test', Zone.HAND)
    trigger = game.stack.top
    assert isinstance(trigger, TriggeredAbilityOnStack)
    assert trigger.source_permanent_id == source.obj_id
