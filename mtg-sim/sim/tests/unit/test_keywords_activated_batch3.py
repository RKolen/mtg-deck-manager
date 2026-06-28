"""Unit tests for activated batch 3: typecycling variants."""

from __future__ import annotations

from engine.abilities.activated.typecycling import (
    has_forestcycling_card,
    has_islandcycling_card,
    has_mountaincycling_card,
    has_plainscycling_card,
    has_swampcycling_card,
    has_typecycling_card,
    has_wizardcycling_card,
    typecycling_cost,
    typecycling_discard_requirement,
    typecycling_mana_needed,
)
from tests.conftest import make_creature, make_instant


def test_forestcycling_card_parses_forest_discard_requirement():
    """Forestcycling cards require discarding a Forest."""
    card = make_creature('Krosan', 4, 3, oracle='Forestcycling {2}')
    assert has_forestcycling_card(card)
    assert has_typecycling_card(card)
    assert typecycling_discard_requirement(card) == 'Forest'
    cost = typecycling_cost(card)
    assert cost is not None
    assert cost.mana_value == 2


def test_islandcycling_card_parses_island_discard_requirement():
    """Islandcycling cards require discarding an Island."""
    card = make_creature('Merfolk', 2, 2, oracle='Islandcycling {1}')
    assert has_islandcycling_card(card)
    assert typecycling_discard_requirement(card) == 'Island'
    assert typecycling_mana_needed(card) == 1


def test_swampcycling_card_detects_swamp_type():
    """Swampcycling cards require discarding a Swamp."""
    card = make_instant('Grave', oracle='Swampcycling {2}\nDestroy target creature.')
    assert has_swampcycling_card(card)
    assert typecycling_discard_requirement(card) == 'Swamp'


def test_mountaincycling_card_detects_mountain_type():
    """Mountaincycling cards require discarding a Mountain."""
    card = make_creature('Goblin', 2, 1, oracle='Mountaincycling {1}')
    assert has_mountaincycling_card(card)
    assert typecycling_discard_requirement(card) == 'Mountain'


def test_plainscycling_card_detects_plains_type():
    """Plainscycling cards require discarding a Plains."""
    card = make_creature('Knight', 3, 3, oracle='Plainscycling {2}')
    assert has_plainscycling_card(card)
    assert typecycling_discard_requirement(card) == 'Plains'


def test_wizardcycling_card_detects_wizard_creature_type():
    """Wizardcycling cards require discarding a Wizard."""
    card = make_creature('Sage', 1, 1, oracle='Wizardcycling {3}')
    assert has_wizardcycling_card(card)
    assert typecycling_discard_requirement(card) == 'Wizard'
    assert not has_forestcycling_card(card)
