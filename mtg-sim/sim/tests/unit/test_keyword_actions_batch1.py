"""Unit tests for keyword actions batch 1.

Bolster, Support, Counter, Detain, Goad, and Investigate.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.counters import (
    bolster_lowest_creature,
    has_bolster,
    has_counter_action,
    has_support,
    support_creatures,
)
from engine.abilities.keywords.actions.resolve import (
    ActionContext,
    _ActionTargets,
    resolve_spell_keyword_actions,
)
from engine.abilities.keywords.actions.specialty import has_detain, has_goad
from engine.abilities.keywords.actions.tokens import has_investigate, investigate
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_bolster_puts_counters_on_lowest_toughness_creature():
    """Bolster adds +1/+1 counters to the lowest-toughness creature."""
    game = fresh_game()
    tough = place_on_battlefield(make_creature('Wall', 1, 5), 0, game.zones)
    frail = place_on_battlefield(make_creature('Sprite', 1, 1), 0, game.zones)
    assert has_bolster('Bolster 2.')
    name = bolster_lowest_creature(game.zones, 0, 2)
    assert name == frail.name
    assert frail.counters.get('+1/+1') == 2
    assert tough.counters.get('+1/+1', 0) == 0


def test_support_puts_counters_on_target_creature():
    """Support adds +1/+1 counters to a chosen creature."""
    game = fresh_game()
    ally = place_on_battlefield(make_creature('Ally', 2, 2), 0, game.zones)
    assert has_support('Support 3 (Put three +1/+1 counters on up to one target creature.)')
    name = support_creatures(game.zones, 0, 3, str(ally.obj_id))
    assert name == ally.name
    assert ally.counters.get('+1/+1') == 3


def test_counter_action_puts_plus_counters_on_creature():
    """Counter as a keyword action places +1/+1 counters."""
    game = fresh_game()
    target = place_on_battlefield(make_creature('Recruit', 1, 1), 0, game.zones)
    oracle = 'Counter target creature (Put a +1/+1 counter on it.)'
    assert has_counter_action(oracle)
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text=oracle,
        targets=_ActionTargets(target_creature_uid=str(target.obj_id)),
    ))
    assert detail is not None
    assert 'counter' in detail.lower()
    assert target.counters.get('+1/+1') == 1


def test_detain_taps_creature_and_marks_detained():
    """Detain taps a creature and marks it detained."""
    game = fresh_game()
    suspect = place_on_battlefield(make_creature('Suspect', 3, 3), 1, game.zones)
    assert has_detain('Detain.')
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Detain',
        targets=_ActionTargets(target_creature_uid=str(suspect.obj_id)),
    ))
    assert detail is not None
    assert 'detained' in detail
    assert suspect.tapped
    assert suspect.counters.get('detained') == 1


def test_goad_marks_creature_as_goaded():
    """Goad marks a creature so it must attack."""
    game = fresh_game()
    brute = place_on_battlefield(make_creature('Brute', 4, 4), 1, game.zones)
    assert has_goad('Goad target creature.')
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Goad',
        targets=_ActionTargets(target_creature_uid=str(brute.obj_id)),
    ))
    assert detail is not None
    assert brute.counters.get('goaded') == 1


def test_investigate_creates_clue_tokens():
    """Investigate creates Clue artifact tokens."""
    game = fresh_game()
    assert has_investigate('Investigate twice.')
    names = investigate(game.zones, 0, 2)
    assert 'Clue Token' in names
    clues = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == 0 and 'Clue' in perm.type_line
    ]
    assert len(clues) == 2
