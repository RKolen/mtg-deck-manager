"""Tests for land mana oracle parsing (Phase H)."""

from __future__ import annotations

from deck_registry import _card_info_from
from engine.cards.land_mana import parse_produced_mana_from_oracle


def test_parse_dual_land_mana():
    """Dual lands infer both colors from oracle text."""
    colors = parse_produced_mana_from_oracle(
        '({T}: Add {U} or {R}.)',
        type_line='Land — Island Mountain',
    )
    assert colors == ['U', 'R']


def test_parse_basic_forest_mana():
    """Basic lands parse a single color from the tap ability."""
    colors = parse_produced_mana_from_oracle(
        '({T}: Add {G}.)',
        type_line='Basic Land — Forest',
    )
    assert colors == ['G']


def test_card_info_fills_produced_mana_when_missing():
    """Deck enrichment backfills produced mana from oracle when Scryfall omits it."""
    card = _card_info_from(
        {
            'name': 'Steam Vents',
            'type_line': 'Land — Island Mountain',
            'oracle_text': '({T}: Add {U} or {R}.)',
            'produced_mana': [],
            'cmc': 0.0,
            'mana_cost': '',
            'pt': '0/0',
        },
        quantity=1,
        sideboard=False,
    )
    assert card.produced_mana == ['U', 'R']
