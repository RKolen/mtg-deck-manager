"""Unit tests for casting batch 41: devoid, harmonize, jump-start, replicate, retrace, spree."""

from __future__ import annotations

from engine.abilities.keywords.casting.devoid import (
    has_devoid_card,
    spell_is_colorless_for_effects,
)
from engine.abilities.keywords.casting.harmonize import (
    can_cast_via_harmonize,
    harmonize_mana_needed,
    has_harmonize_card,
)
from engine.abilities.keywords.casting.jump_start import (
    can_cast_via_jump_start,
    has_jump_start_card,
    jump_start_mana_needed,
)
from engine.abilities.keywords.casting.replicate import (
    has_replicate_card,
    replicate_extra_mana,
    supports_replicate_copies,
)
from engine.abilities.keywords.casting.retrace import (
    can_cast_via_retrace,
    has_retrace_card,
    retrace_mana_needed,
)
from engine.abilities.keywords.casting.spree import (
    has_spree_card,
    spree_extra_mana,
    spree_modes,
)
from tests.conftest import make_instant


def test_devoid_keyword_marks_spell_colorless():
    """Devoid card detection treats the spell as colorless for effects."""
    card = make_instant(
        'Slip',
        mana_cost='{1}{U}{U}',
        oracle='Devoid\nCounter target spell.',
    )
    assert has_devoid_card(card)
    assert spell_is_colorless_for_effects(card)


def test_harmonize_keyword_parses_graveyard_cost():
    """Harmonize card detection and alternate cost from graveyard."""
    card = make_instant('Refrain', oracle='Harmonize {3}{G}\nReturn target creature.')
    assert has_harmonize_card(card)
    assert harmonize_mana_needed(card) == (4, 0)
    assert can_cast_via_harmonize(card, 'main1', stack_is_empty=True)


def test_jump_start_keyword_allows_graveyard_flash_timing():
    """Jump-start card detection and instant-speed graveyard cast."""
    card = make_instant(
        'Witch',
        oracle='Jump-start {2}{R}\nWitch deals 3 damage.',
    )
    assert has_jump_start_card(card)
    assert jump_start_mana_needed(card) == 3
    assert can_cast_via_jump_start(card, 'attack', stack_is_empty=False)


def test_replicate_keyword_charges_per_extra_copy():
    """Replicate card detection and per-copy extra mana."""
    card = make_instant('Shriek', oracle='Replicate {1}{U}\nDraw a card.')
    assert has_replicate_card(card)
    assert supports_replicate_copies(card)
    assert replicate_extra_mana(card, 2) == 4


def test_retrace_keyword_uses_printed_mana_cost():
    """Retrace card detection and normal mana cost from graveyard."""
    card = make_instant(
        'Worm',
        cmc=3,
        mana_cost='{2}{G}',
        oracle='Draw two cards.\nRetrace',
    )
    assert has_retrace_card(card)
    assert retrace_mana_needed(card) == 3
    assert can_cast_via_retrace(card, 'main2', stack_is_empty=True)


def test_spree_keyword_sums_chosen_mode_costs():
    """Spree card detection and mana for multiple chosen modes."""
    card = make_instant(
        'Heist',
        oracle=(
            'Spree\n'
            '• {1} — Create a Treasure token.\n'
            '• {2} — Draw a card.'
        ),
    )
    assert has_spree_card(card)
    modes = spree_modes(card)
    assert len(modes) == 2
    assert spree_extra_mana(card, (0, 1)) == 3
