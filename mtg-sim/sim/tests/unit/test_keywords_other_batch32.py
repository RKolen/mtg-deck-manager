"""Unit tests for batch 32 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.other.choose_a_background import (
    has_choose_a_background,
    validate_choose_a_background_deck,
)
from engine.abilities.keywords.other.doctors_companion import (
    has_doctors_companion,
    validate_doctors_companion_deck,
)
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.friends_forever import (
    has_friends_forever,
    validate_friends_forever_deck,
)
from engine.abilities.keywords.other.hidden_agenda import (
    apply_hidden_agenda_on_spell_cast,
    has_hidden_agenda,
    register_hidden_agenda,
    reveal_hidden_agenda,
)
from engine.abilities.keywords.other.job_select import has_job_select
from tests.conftest import _CardStats, fresh_game, make_card, place_on_battlefield


def test_choose_a_background_requires_background():
    """Choose a Background decks must include a legendary Background."""
    commander = make_card(
        name='Gale',
        type_line='Legendary Creature — Human Wizard',
        oracle='Choose a background',
    )
    background = make_card(
        name='Soldier Story',
        type_line='Legendary Enchantment — Background',
        oracle='Commander',
    )
    assert has_choose_a_background(commander)
    assert validate_choose_a_background_deck([commander]) is not None
    assert validate_choose_a_background_deck([commander, background]) is None


def test_doctors_companion_requires_time_lord_doctor():
    """Doctor's companion decks must include a Time Lord Doctor."""
    companion = make_card(
        name='Susan',
        type_line='Legendary Creature — Human',
        oracle="Doctor's companion",
    )
    doctor = make_card(
        name='The Doctor',
        type_line='Legendary Creature — Time Lord Doctor',
        oracle='',
    )
    assert has_doctors_companion(companion)
    assert validate_doctors_companion_deck([companion]) is not None
    assert validate_doctors_companion_deck([companion, doctor]) is None


def test_friends_forever_requires_two_commanders():
    """Friends forever decks need two friends-forever commanders."""
    first = make_card(
        name='Will',
        type_line='Legendary Creature — Human',
        oracle='Friends forever',
    )
    second = make_card(
        name='Rowan',
        type_line='Legendary Creature — Human',
        oracle='Friends forever',
    )
    assert has_friends_forever(first)
    assert validate_friends_forever_deck([first]) is not None
    assert validate_friends_forever_deck([first, second]) is None


def test_hidden_agenda_matches_revealed_spell_name():
    """Hidden agenda logs when a revealed agenda matches a cast spell."""
    game = fresh_game()
    card = make_card(
        name='Conspiracy',
        type_line='Enchantment',
        oracle='Hidden agenda',
    )
    assert has_hidden_agenda(card)
    register_hidden_agenda(game, 0, 'Lightning Bolt')
    assert reveal_hidden_agenda(game, 0) is not None
    details = apply_hidden_agenda_on_spell_cast(game, 0, 'Lightning Bolt')
    assert details
    assert 'hidden agenda matched' in details[0]


def test_job_select_creates_hero_and_attaches():
    """Job select ETB creates a Hero token and attaches the equipment."""
    game = fresh_game()
    gear = place_on_battlefield(
        make_card(
            name='Power Suit',
            type_line='Artifact — Equipment',
            oracle='Job select',
            stats=_CardStats(cmc=3.0, pt='0/0'),
        ),
        0,
        game.zones,
    )
    assert has_job_select(gear)
    details = apply_etb_other_abilities(game, gear)
    assert details
    assert any('job select' in item for item in details)
    assert gear.attached_to is not None
    host = game.zones.find_permanent(gear.attached_to)
    assert host is not None
    assert 'Hero' in host.type_line
