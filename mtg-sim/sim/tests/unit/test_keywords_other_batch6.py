"""Unit tests for ability_other batch 6: riot, mentor, exalted."""

from __future__ import annotations

from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.exalted import apply_exalted_on_attack
from engine.abilities.keywords.other.mentor import apply_mentor_on_attack
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_riot_puts_counter_on_etb():
    """Riot adds a +1/+1 counter on ETB."""
    game = fresh_game()
    creature = place_on_battlefield(
        make_creature('Goblin', 1, 1, oracle='Riot'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, creature)
    assert any('riot' in detail for detail in details)
    assert creature.counters.get('+1/+1') == 1


def test_mentor_buffs_smaller_attacker():
    """Mentor puts +1/+1 on another attacking creature with less power."""
    game = fresh_game()
    mentor = place_on_battlefield(
        make_creature('Mentor', 4, 4, oracle='Mentor'),
        0,
        game.zones,
        sick=False,
    )
    rookie = place_on_battlefield(
        make_creature('Rookie', 2, 2),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_mentor_on_attack(
        game,
        mentor,
        [str(mentor.obj_id), str(rookie.obj_id)],
    )
    assert detail is not None
    assert rookie.counters.get('+1/+1') == 1


def test_exalted_solo_attack():
    """Exalted grants +1/+1 when this creature attacks alone."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Knight', 2, 2, oracle='Exalted'),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_exalted_on_attack(game, attacker, solo_attack=True)
    assert detail is not None
    assert attacker.counters.get('+1/+1') == 1
