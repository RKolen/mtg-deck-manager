"""Unit tests for batch 44 infra: register and etb_handlers."""

from __future__ import annotations

from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.etb_handlers import etb_detail_producer_count
from engine.abilities.keywords.other.register import (
    register_permanent_other_keywords,
    trigger_registration_count,
)
from engine.rules.triggers import TriggerKey
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_register_skips_permanent_without_oracle_text():
    """Register ignores permanents with no oracle text."""
    game = fresh_game()
    blank = place_on_battlefield(make_creature('Bear', 2, 2, oracle=''), 0, game.zones)
    register_permanent_other_keywords(blank, game.trigger_registry)
    assert trigger_registration_count(game.trigger_registry, blank) == 0


def test_register_wires_evolve_enters_battlefield_trigger():
    """Register adds an enters-the-battlefield trigger for evolve."""
    game = fresh_game()
    evolver = place_on_battlefield(
        make_creature('Shambleshark', 1, 1, oracle='Evolve'),
        0,
        game.zones,
    )
    register_permanent_other_keywords(evolver, game.trigger_registry)
    assert trigger_registration_count(
        game.trigger_registry,
        evolver,
        trigger_key=TriggerKey.ENTERS_BATTLEFIELD,
    ) == 1


def test_register_wires_cipher_spell_cast_trigger():
    """Register adds a spell-cast trigger for cipher."""
    game = fresh_game()
    host = place_on_battlefield(
        make_creature('Host', 1, 1, oracle='Cipher — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_other_keywords(host, game.trigger_registry)
    assert trigger_registration_count(
        game.trigger_registry,
        host,
        trigger_key=TriggerKey.SPELL_CAST,
    ) == 1


def test_register_wires_exploit_enters_battlefield_trigger():
    """Register adds an enters-the-battlefield trigger for exploit."""
    game = fresh_game()
    exploiter = place_on_battlefield(
        make_creature('Butcher', 3, 3, oracle='Exploit\nDraw a card.'),
        0,
        game.zones,
    )
    register_permanent_other_keywords(exploiter, game.trigger_registry)
    assert trigger_registration_count(
        game.trigger_registry,
        exploiter,
        trigger_key=TriggerKey.ENTERS_BATTLEFIELD,
    ) == 1


def test_etb_handlers_wires_expected_producer_count():
    """ETB handlers expose one producer per wired keyword hook."""
    assert etb_detail_producer_count() == 36


def test_etb_handlers_runs_soulbond_producer_on_entry():
    """ETB handlers route soulbond through apply_etb_other_abilities."""
    game = fresh_game()
    place_on_battlefield(
        make_creature('Partner', 2, 2, oracle='Soulbond'),
        0,
        game.zones,
    )
    soulbond = place_on_battlefield(
        make_creature('Bondmate', 2, 2, oracle='Soulbond'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, soulbond)
    assert any('soulbond' in line.lower() for line in details)


def test_etb_handlers_runs_encore_producer_on_entry():
    """ETB handlers mark encore permanents through apply_etb_other_abilities."""
    game = fresh_game()
    drummer = place_on_battlefield(
        make_creature('Drum', 3, 3, oracle='Encore {5}{U}'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, drummer)
    assert any('encore' in line.lower() for line in details)
    assert drummer.counters.get('encore') == 1
