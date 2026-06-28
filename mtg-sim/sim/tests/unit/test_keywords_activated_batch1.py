"""Unit tests for activated batch 1: cycling, channel, crew, mount, unearth, level up."""

from __future__ import annotations

from engine.abilities.activated.card_keyword_abilities import (
    can_unearth,
    channel_draw,
    channel_effect,
    cycling_cost,
    has_channel_card,
    has_cycling_card,
    has_unearth_card,
    unearth_mana_needed,
)
from engine.abilities.activated.crew import crew_cost, has_crew_card
from engine.abilities.activated.level_up import has_level_up_card, level_up_mana_needed
from engine.abilities.activated.mount import has_mount_card, mount_cost
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_cycling_card_parses_discard_cost():
    """Cycling card detection and alternate discard cost."""
    card = make_instant('Wastes', oracle='Cycling {2}\nDraw a card.')
    assert has_cycling_card(card)
    cost = cycling_cost(card)
    assert cost is not None
    assert cost.mana_value == 2
    assert not has_cycling_card(make_instant('Bolt', oracle='Deal 3 damage.'))


def test_channel_card_parses_mana_and_draw_effect():
    """Channel card detection and effect text after the cost."""
    card = make_instant(
        'Boseiju',
        oracle='Channel — {1}{G}, Discard Boseiju: Draw two cards.',
    )
    assert has_channel_card(card)
    effect = channel_effect(card)
    assert channel_draw(effect) == 2


def test_crew_card_requires_vehicle_type_line():
    """Crew card detection applies only to vehicles."""
    vehicle = make_card(
        'Skiff',
        type_line='Artifact — Vehicle',
        oracle='Crew 2',
        stats=_CardStats(pt='3/3'),
    )
    assert has_crew_card(vehicle)
    assert not has_crew_card(make_creature('Pilot', 2, 2, oracle='Crew 2'))
    vehicle_perm = place_on_battlefield(vehicle, 0, fresh_game().zones)
    assert crew_cost(vehicle_perm) == 2


def test_mount_card_requires_mount_creature():
    """Mount card detection applies only to mount creatures."""
    mount = make_card(
        'Steed',
        type_line='Creature — Mount',
        oracle='Mount 2',
        stats=_CardStats(cmc=2.0, pt='2/2'),
    )
    assert has_mount_card(mount)
    game = fresh_game()
    mount_perm = place_on_battlefield(mount, 0, game.zones)
    assert mount_cost(mount_perm) == 2


def test_unearth_card_allows_main_phase_from_graveyard():
    """Unearth card detection and graveyard activation timing."""
    creature = make_creature('Crawler', 2, 2, oracle='Unearth {B}')
    assert has_unearth_card(creature)
    assert unearth_mana_needed(creature) == 1
    assert can_unearth(creature, 'main2', stack_is_empty=True)
    assert not can_unearth(creature, 'attack', stack_is_empty=True)


def test_level_up_card_parses_creature_activation_cost():
    """Level up card detection and mana for the activated ability."""
    card = make_creature('Student', 1, 1, oracle='Level up {1}')
    assert has_level_up_card(card)
    perm = place_on_battlefield(card, 0, fresh_game().zones)
    assert level_up_mana_needed(perm) == 1
