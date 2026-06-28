"""Unit tests for casting batch 39: buyback, casualty, cleave, conspire, demonstrate, disturb."""

from __future__ import annotations

from engine.abilities.keywords.casting.buyback import (
    buyback_extra_mana,
    has_buyback_card,
    normalize_buyback,
)
from engine.abilities.keywords.casting.casualty import (
    casualty_sacrifice_error,
    has_casualty_card,
    supports_casualty_copies,
)
from engine.abilities.keywords.casting.cleave import (
    cleave_mana_needed,
    has_cleave_card,
    supports_cleave_copies,
)
from engine.abilities.keywords.casting.conspire import (
    conspire_color_match,
    has_conspire_card,
    supports_conspire_copies,
)
from engine.abilities.keywords.casting.demonstrate import (
    has_demonstrate_card,
    supports_demonstrate_copies,
)
from engine.abilities.keywords.casting.disturb import (
    can_cast_via_disturb,
    disturb_mana_needed,
    has_disturb_card,
)
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_buyback_keyword_adds_extra_mana_when_paid():
    """Buyback card detection and extra mana when buyback is paid."""
    card = make_instant('Capsize', oracle='Buyback {1}\nReturn target creature to its hand.')
    assert has_buyback_card(card)
    assert normalize_buyback(card, True)
    assert buyback_extra_mana(card, True) == 1


def test_casualty_keyword_validates_creature_sacrifice():
    """Casualty card detection and sacrifice power validation."""
    game = fresh_game()
    spell = make_instant('Rite', oracle='Casualty 2\nDraw two cards.')
    assert has_casualty_card(spell)
    assert supports_casualty_copies(spell)
    weak = place_on_battlefield(make_creature('Weak', 1, 1), 0, game.zones)
    casualty_err = casualty_sacrifice_error(game.zones, 0, spell, True, [weak.obj_id])
    assert casualty_err is not None


def test_cleave_keyword_parses_alternate_cost():
    """Cleave card detection and alternate cost parsing."""
    card = make_instant(
        'Torch',
        oracle='Cleave {2}{R}\nTorch the Tower deals 2 damage.',
    )
    assert has_cleave_card(card)
    assert supports_cleave_copies(card)
    assert cleave_mana_needed(card)[0] == 3


def test_conspire_keyword_matches_creature_colors():
    """Conspire card detection and color-matching creature requirement."""
    game = fresh_game()
    spell = make_instant(
        'Twin',
        mana_cost='{U}{U}',
        oracle='Conspire\nDraw a card.',
    )
    assert has_conspire_card(spell)
    assert supports_conspire_copies(spell)
    assert not conspire_color_match(spell, game.zones, 0)
    place_on_battlefield(
        make_creature('Wizard', 1, 1, mana_cost='{U}'),
        0,
        game.zones,
    )
    assert conspire_color_match(spell, game.zones, 0)


def test_demonstrate_keyword_supports_spell_copies():
    """Demonstrate card detection and copy support on instants."""
    spell = make_instant('Lesson', oracle='Demonstrate\nDraw a card.')
    assert has_demonstrate_card(spell)
    assert supports_demonstrate_copies(spell)
    creature = make_creature('Bear', 2, 2, oracle='Demonstrate')
    assert not has_demonstrate_card(creature)


def test_disturb_keyword_casts_from_graveyard_timing():
    """Disturb card detection, cost parsing, and timing."""
    card = make_creature('Geist', 2, 2, oracle='Disturb {2}{U}\nFlying')
    assert has_disturb_card(card)
    assert disturb_mana_needed(card) == 3
    assert can_cast_via_disturb(card, 'main1', True)
