"""Unit tests for casting batch 40: entwine, escalate, freerunning, miracle, mutate, overload."""

from __future__ import annotations

from engine.abilities.keywords.casting.entwine import (
    cast_mana_with_entwine,
    has_entwine_card,
    normalize_entwined,
)
from engine.abilities.keywords.casting.escalate import (
    escalate_extra_mana,
    has_escalate_card,
)
from engine.abilities.keywords.casting.freerunning import (
    freerunning_mana_needed,
    has_freerunning_card,
    normalize_freerunning_cast,
)
from engine.abilities.keywords.casting.miracle import (
    has_miracle_card,
    miracle_mana_needed,
    normalize_miracle_cast,
)
from engine.abilities.keywords.casting.mutate import (
    has_mutate_card,
    mutate_host_error,
    mutate_mana_needed,
)
from engine.abilities.keywords.casting.overload import (
    has_overload_card,
    normalize_overloaded,
    overload_opponent_indices,
)
from tests.conftest import fresh_game, make_card, make_creature, make_instant, place_on_battlefield


def test_entwine_keyword_adds_mana_when_paid():
    """Entwine card detection and extra mana when entwine is paid."""
    card = make_instant(
        'Pain',
        oracle='Choose one — • Pain deals 3 damage. • Draw a card.\nEntwine {2}',
    )
    assert has_entwine_card(card)
    assert normalize_entwined(card, True)
    mana, _life = cast_mana_with_entwine(card, 3, 0, entwined=True)
    assert mana == 5


def test_escalate_keyword_charges_per_extra_target():
    """Escalate card detection and per-target extra mana."""
    card = make_instant('Collective', oracle='Escalate {1}\nTarget player draws a card.')
    assert has_escalate_card(card)
    assert escalate_extra_mana(card, 2) == 2


def test_freerunning_keyword_available_after_combat_damage():
    """Freerunning card detection and alternate cost when available."""
    card = make_instant('Slither', oracle='Freerunning {0}\nDeal 2 damage.')
    assert has_freerunning_card(card)
    assert freerunning_mana_needed(card) == (0, 0)
    assert normalize_freerunning_cast(card, True, freerunning_available=True)


def test_miracle_keyword_uses_reduced_cost():
    """Miracle card detection and reduced cast cost."""
    card = make_instant('Terminus', oracle='Miracle {W}\nDestroy all creatures.')
    assert has_miracle_card(card)
    assert normalize_miracle_cast(card, True)
    assert miracle_mana_needed(card) == (1, 0)


def test_mutate_keyword_targets_non_human_host():
    """Mutate card detection and non-Human host validation."""
    game = fresh_game()
    card = make_creature(
        'Snapdax',
        3,
        3,
        oracle='Mutate {2}{W}{B}{R}\nMutate onto a non-Human creature.',
    )
    assert has_mutate_card(card)
    assert mutate_mana_needed(card) == (5, 0)
    host = place_on_battlefield(
        make_card(name='Cat', type_line='Creature — Cat'),
        0,
        game.zones,
    )
    assert mutate_host_error(game.zones, 0, card, str(host.obj_id)) is None


def test_overload_keyword_hits_each_opponent():
    """Overload card detection and opponent targeting when overloaded."""
    card = make_instant('Charm', oracle='Overload {3}{U}{U}\nCounter target spell.')
    assert has_overload_card(card)
    assert normalize_overloaded(card, True)
    assert overload_opponent_indices(0) == [1]
