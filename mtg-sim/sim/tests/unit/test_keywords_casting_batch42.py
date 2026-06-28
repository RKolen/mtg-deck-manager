"""Unit tests for casting batch 42: blitz, dash, embalm, evoke."""

from __future__ import annotations

from engine.abilities.keywords.casting.blitz import (
    blitz_mana_needed,
    has_blitz_card,
    normalize_blitz_cast,
)
from engine.abilities.keywords.casting.dash import (
    dash_mana_needed,
    has_dash_card,
    normalize_dash_cast,
)
from engine.abilities.keywords.casting.embalm import (
    can_embalm,
    embalm_mana_needed,
    has_embalm_card,
)
from engine.abilities.keywords.casting.evoke import (
    evoke_mana_needed,
    has_evoke_card,
    normalize_evoke_cast,
)
from tests.conftest import make_creature, make_instant


def test_blitz_card_helper_rejects_non_creatures():
    """Blitz card detection applies only to creature spells."""
    creature = make_creature('Racer', 2, 1, oracle='Blitz {R}')
    instant = make_instant('Shock', oracle='Blitz {R}\nDeal 2 damage.')
    assert has_blitz_card(creature)
    assert not has_blitz_card(instant)
    assert normalize_blitz_cast(creature, True)
    assert blitz_mana_needed(creature) == (1, 0)


def test_dash_card_helper_parses_alternate_cost():
    """Dash card detection and alternate cost for creatures."""
    creature = make_creature('Courier', 1, 1, oracle='Dash {1}{R}')
    assert has_dash_card(creature)
    assert not has_dash_card(make_instant('Bolt', oracle='Deal 3 damage.'))
    assert normalize_dash_cast(creature, False) is False
    assert dash_mana_needed(creature) == (2, 0)


def test_embalm_card_helper_allows_main_phase_activation():
    """Embalm card detection and sorcery-speed activation window."""
    creature = make_creature('Steward', 3, 3, oracle='Embalm {3}{W}')
    assert has_embalm_card(creature)
    assert embalm_mana_needed(creature) == (4, 0)
    assert can_embalm(creature, 'main1', stack_is_empty=True)
    assert not can_embalm(creature, 'attack', stack_is_empty=False)


def test_evoke_card_helper_parses_sacrifice_cost():
    """Evoke card detection and alternate sacrifice cost."""
    creature = make_creature('Shade', 3, 3, oracle='Evoke {U}')
    assert has_evoke_card(creature)
    assert normalize_evoke_cast(creature, True)
    assert evoke_mana_needed(creature) == (1, 0)
    assert not has_evoke_card(make_instant('Counter', oracle='Counter target spell.'))
