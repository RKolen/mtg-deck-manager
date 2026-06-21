"""Unit tests for increment, max speed, and solved (batch 30)."""

from __future__ import annotations

from engine.abilities.keywords.combat import can_attack
from engine.abilities.keywords.other.increment import (
    apply_increment_on_spell_cast,
    has_increment,
    increment_triggers,
)
from engine.abilities.keywords.other.max_speed import (
    has_max_speed,
    max_speed_blocks_attack,
    max_speed_grants_haste,
)
from engine.abilities.keywords.other.solved import (
    has_to_solve,
    is_solved,
    resolve_to_solve_end_step,
    to_solve_condition_met,
)
from tests.conftest import _CardStats, fresh_game, make_card, make_creature, place_on_battlefield


def test_increment_puts_counter_when_mana_exceeds_stats():
    """Increment adds a +1/+1 counter when enough mana was spent."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Scholar', 1, 1, oracle='Increment'),
        0,
        game.zones,
    )
    assert has_increment(perm)
    assert increment_triggers(perm, 3)
    spell = make_creature('Bolt', 2, 2)
    details = apply_increment_on_spell_cast(game, 0, spell, mana_spent=3)
    assert details
    assert perm.counters.get('+1/+1', 0) == 1


def test_max_speed_gates_attack_and_grants_haste():
    """Max speed creatures need speed 4 to attack and may gain haste."""
    game = fresh_game()
    racer = place_on_battlefield(
        make_creature(
            'Racer',
            3,
            3,
            oracle=(
                "Max speed — This creature has haste.\n"
                "This creature can't attack unless you have max speed."
            ),
        ),
        0,
        game.zones,
    )
    racer.sick = True
    assert max_speed_blocks_attack(racer, game)
    assert not can_attack(racer, game)
    game.players[0].speed = 4
    assert has_max_speed(game, 0)
    assert max_speed_grants_haste(racer, game)
    assert can_attack(racer, game)


def test_solved_case_marks_at_end_step():
    """A Case becomes solved when its to solve condition is met."""
    game = fresh_game()
    for idx in range(3):
        place_on_battlefield(
            make_card(
                name=f'Detective {idx}',
                type_line='Creature — Human Detective',
                oracle='',
                mana_cost='{1}{W}',
                stats=_CardStats(cmc=2.0, pt='2/2'),
            ),
            0,
            game.zones,
        )
    case = place_on_battlefield(
        make_card(
            name='Pilfered Proof',
            type_line='Enchantment — Case',
            oracle=(
                'When this Case enters, create a 2/2 Detective.\n'
                'To solve — You control three or more Detectives.\n'
                'Solved — Creatures you control get +1/+1.'
            ),
            mana_cost='{2}{W}',
            stats=_CardStats(cmc=3.0, pt='0/0'),
        ),
        0,
        game.zones,
    )
    assert has_to_solve(case)
    assert to_solve_condition_met(game, case)
    details = resolve_to_solve_end_step(game, 0)
    assert any('solved' in line for line in details)
    assert is_solved(case)
