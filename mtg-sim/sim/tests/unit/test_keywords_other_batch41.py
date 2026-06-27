"""Unit tests for batch 41 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.other.companion import (
    find_companion_in_deck,
    has_companion_card,
    validate_companion_deck,
)
from engine.abilities.keywords.other.encore import has_encore_card
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.eternalize import (
    apply_eternalize_from_graveyard,
    has_eternalize_card,
)
from engine.abilities.keywords.other.morph import (
    apply_turn_up_morph,
    has_morph_card,
    normalize_morph_cast,
)
from engine.abilities.keywords.other.ninjutsu import apply_ninjutsu, has_ninjutsu_card
from engine.abilities.keywords.other.partner import has_partner_card, validate_partner_deck
from engine.core.game_object import CardObject
from tests.conftest import (
    _CardStats,
    add_to_hand,
    fresh_game,
    make_card,
    make_creature,
    place_on_battlefield,
)


def test_morph_keyword_supports_face_down_cast():
    """Morph card detection and face-down cast normalization."""
    card = make_creature('Shifter', 3, 3, oracle='Morph {2}{G}')
    assert has_morph_card(card)
    assert normalize_morph_cast(card, cast_for_morph=True)
    game = fresh_game()
    shifter = place_on_battlefield(card, 0, game.zones)
    shifter.face_down = True
    morph_detail = apply_turn_up_morph(shifter)
    assert morph_detail is not None
    assert not shifter.face_down


def test_ninjutsu_keyword_swaps_attacker_for_ninja():
    """Ninjutsu card detection and attacker replacement."""
    game = fresh_game()
    scout = place_on_battlefield(make_creature('Scout', 1, 1), 0, game.zones, sick=False)
    ninja_card = make_creature('Shinobi', 2, 2, oracle='Ninjutsu {1}{U}')
    assert has_ninjutsu_card(ninja_card)
    add_to_hand(ninja_card, 0, game.zones)
    ninjutsu_detail = apply_ninjutsu(
        game,
        game.zones,
        0,
        0,
        str(scout.obj_id),
    )
    assert ninjutsu_detail is not None
    assert game.zones.find_permanent(scout.obj_id) is None


def test_encore_keyword_marks_creature_on_etb():
    """Encore card detection and ETB marker through registration."""
    game = fresh_game()
    card = make_creature('Drum', 4, 4, oracle='Encore {3}{B}')
    assert has_encore_card(card)
    drummer = place_on_battlefield(card, 0, game.zones)
    etb_lines = apply_etb_other_abilities(game, drummer)
    assert any('encore' in line for line in etb_lines)
    assert drummer.counters.get('encore') == 1


def test_eternalize_keyword_creates_exile_token():
    """Eternalize card detection and token creation from graveyard."""
    game = fresh_game()
    eternal_card = make_creature('Monk', 2, 2, oracle='Eternalize {3}{W}')
    assert has_eternalize_card(eternal_card)
    game.zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=eternal_card),
    )
    eternalize_detail = apply_eternalize_from_graveyard(game.zones, 0, 0)
    assert eternalize_detail is not None
    assert len(game.zones.player_zones[0].exile) >= 1


def test_partner_keyword_requires_two_partners_in_deck():
    """Partner card detection and two-partner deck validation."""
    lone = make_creature('Solo', 3, 3, oracle='Partner')
    assert has_partner_card(lone)
    assert validate_partner_deck([lone]) is not None
    mate = make_creature('Mate', 2, 2, oracle='Partner')
    assert validate_partner_deck([lone, mate]) is None


def test_companion_keyword_validates_deck_restriction():
    """Companion card detection and deck restriction validation."""
    companion_oracle = (
        'Companion — Your deck contains only creature cards, '
        'each with mana value 3 or greater.'
    )
    companion = make_card(
        'Lurrus',
        type_line='Creature — Cat Nightmare',
        oracle=companion_oracle,
        stats=_CardStats(cmc=3.0, pt='3/3'),
    )
    assert has_companion_card(companion)
    valid_deck = [
        companion,
        make_card('Bear', type_line='Creature — Bear', stats=_CardStats(cmc=3.0, pt='3/3')),
    ]
    assert find_companion_in_deck(valid_deck) is companion
    assert validate_companion_deck(valid_deck) is None
