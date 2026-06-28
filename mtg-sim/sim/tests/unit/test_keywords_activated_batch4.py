"""Unit tests for activated batch 4: remaining typecycling variants."""

from __future__ import annotations

from engine.abilities.activated.card_keyword_abilities import has_cycling_card
from engine.abilities.activated.typecycling import (
    has_basic_landcycling_card,
    has_landcycling_card,
    has_slivercycling_card,
    has_typecycling_card,
    has_typecycling_keyword_card,
    typecycling_discard_requirement,
    typecycling_mana_needed,
)
from tests.conftest import make_creature, make_instant


def test_basic_landcycling_card_requires_basic_land_discard():
    """Basic landcycling cards require discarding a basic land."""
    card = make_creature('Wayfarer', 3, 2, oracle='Basic landcycling {1}')
    assert has_basic_landcycling_card(card)
    assert has_typecycling_card(card)
    assert typecycling_discard_requirement(card) == 'Basic Land'
    assert typecycling_mana_needed(card) == 1


def test_landcycling_card_requires_any_land_discard():
    """Landcycling cards require discarding any land."""
    card = make_instant('Expedition', oracle='Landcycling {2}\nDraw a card.')
    assert has_landcycling_card(card)
    assert typecycling_discard_requirement(card) == 'Land'


def test_slivercycling_card_requires_sliver_discard():
    """Slivercycling cards require discarding a Sliver."""
    card = make_creature('Hive', 2, 2, oracle='Slivercycling {3}')
    assert has_slivercycling_card(card)
    assert typecycling_discard_requirement(card) == 'Sliver'


def test_typecycling_keyword_card_marks_named_type_discard():
    """Typecycling cards discard a card of the named type."""
    card = make_creature(
        'Dragon',
        5,
        5,
        oracle='Typecycling {2} (Discard a Dragon card.)',
    )
    assert has_typecycling_keyword_card(card)
    assert typecycling_discard_requirement(card) == 'Type'
    assert not has_slivercycling_card(card)


def test_plain_cycling_is_not_typecycling():
    """Generic cycling does not register as typecycling."""
    card = make_instant('Wastes', oracle='Cycling {2}\nDraw a card.')
    assert has_cycling_card(card)
    assert not has_typecycling_card(card)
    assert typecycling_discard_requirement(card) is None


def test_landcycling_does_not_match_basic_landcycling_helper():
    """Landcycling and basic landcycling are distinct registry keywords."""
    land = make_creature('Nomad', 2, 1, oracle='Landcycling {2}')
    basic = make_creature('Scout', 2, 1, oracle='Basic landcycling {1}')
    assert has_landcycling_card(land)
    assert not has_basic_landcycling_card(land)
    assert has_basic_landcycling_card(basic)
    assert not has_landcycling_card(basic)
