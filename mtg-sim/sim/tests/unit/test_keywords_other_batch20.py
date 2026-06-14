"""Unit tests for graft, amplify, and frenzy (batch 20)."""

from __future__ import annotations

from engine.abilities.keywords.other.amplify import apply_amplify_etb
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.frenzy import apply_frenzy_on_unblocked_attack
from engine.abilities.keywords.other.graft import apply_graft_etb
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_card, make_creature, place_on_battlefield


def test_graft_moves_counter_from_donor():
    """Graft moves one +1/+1 counter from another creature."""
    game = fresh_game()
    donor = place_on_battlefield(make_creature('Donor', 2, 2), 0, game.zones)
    donor.counters['+1/+1'] = 2
    grafted = place_on_battlefield(
        make_creature('Grafted', 1, 1, oracle='Graft'),
        0,
        game.zones,
    )
    detail = apply_graft_etb(game, grafted)
    assert detail is not None
    assert grafted.counters.get('+1/+1', 0) == 1
    assert donor.counters.get('+1/+1', 0) == 1


def test_amplify_counts_matching_hand_creatures():
    """Amplify adds counters for each matching creature in hand."""
    game = fresh_game()
    game.zones.player_zones[0].hand.append(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_card('Human Ally', type_line='Creature — Human'),
        ),
    )
    amplified = place_on_battlefield(
        make_card('Leader', type_line='Creature — Human', oracle='Amplify 1'),
        0,
        game.zones,
    )
    detail = apply_amplify_etb(game, amplified)
    assert detail is not None
    assert amplified.counters.get('+1/+1', 0) == 1


def test_frenzy_on_unblocked_attack():
    """Frenzy triggers when a creature attacks unblocked."""
    game = fresh_game()
    frenzied = place_on_battlefield(
        make_creature(
            'Berserker',
            3,
            2,
            oracle="Frenzy (Whenever this attacks and isn't blocked, draw a card.)",
        ),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_frenzy_on_unblocked_attack(game, frenzied, blocked=False)
    assert detail is not None
    assert 'draw' in detail


def test_graft_etb_hook_runs_from_registry():
    """Graft is wired through apply_etb_other_abilities."""
    game = fresh_game()
    donor = place_on_battlefield(make_creature('Donor', 2, 2), 0, game.zones)
    donor.counters['+1/+1'] = 1
    grafted = place_on_battlefield(
        make_creature('Grafted', 1, 1, oracle='Graft'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, grafted)
    assert any('graft' in line for line in details)
