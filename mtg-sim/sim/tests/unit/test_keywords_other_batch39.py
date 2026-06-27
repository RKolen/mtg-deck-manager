"""Unit tests for batch 39 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.combat import can_attack
from engine.abilities.keywords.other.ascend import has_ascend_card, update_ascend_status
from engine.abilities.keywords.other.boast import apply_boast, has_boast_card
from engine.abilities.keywords.other.decayed import apply_decayed_etb, has_decayed_card
from engine.abilities.keywords.other.echo import apply_echo_etb, has_echo_card
from engine.abilities.keywords.other.myriad import apply_myriad_on_attack, has_myriad_card
from engine.abilities.keywords.other.outlast import apply_outlast, has_outlast_card
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_echo_keyword_marks_upkeep_debt_on_etb():
    """Echo card detection and upkeep marker when the creature enters."""
    card = make_creature('Raptor', 4, 4, oracle='Echo {2}{G}{G}')
    assert has_echo_card(card)
    raptor = place_on_battlefield(card, 0, fresh_game().zones)
    echo_detail = apply_echo_etb(raptor)
    assert echo_detail is not None
    assert raptor.counters.get('echo') == 1


def test_decayed_creature_cannot_attack_after_etb():
    """Decayed keyword detection and attack restriction marker."""
    card = make_creature('Walker', 2, 2, oracle='Decayed')
    assert has_decayed_card(card)
    walker = place_on_battlefield(card, 0, fresh_game().zones)
    decay_detail = apply_decayed_etb(walker)
    assert decay_detail is not None
    assert not can_attack(walker)


def test_ascend_grants_citys_blessing_at_ten_permanents():
    """Ascend keyword detection and City's Blessing at ten permanents."""
    game = fresh_game()
    card = make_creature('Cleric', 2, 2, oracle='Ascend')
    assert has_ascend_card(card)
    for index in range(10):
        place_on_battlefield(make_creature(f'Permanent {index}', 1, 1), 0, game.zones)
    ascend_detail = update_ascend_status(game, 0)
    assert ascend_detail is not None
    assert game.players[0].ascended


def test_boast_draws_when_oracle_requests_it():
    """Boast keyword detection and simplified draw effect."""
    card = make_creature(
        'Boaster',
        2,
        2,
        oracle='{1}: Boast — Draw a card.',
    )
    assert has_boast_card(card)
    boaster = place_on_battlefield(card, 0, fresh_game().zones)
    drawn: list[object] = []

    def _draw(player_idx: int, count: int) -> list[object]:
        assert player_idx == 0
        assert count == 1
        return drawn

    boast_detail = apply_boast(boaster, 0, _draw)
    assert boast_detail is not None
    assert 'drew' in boast_detail


def test_outlast_adds_counter_once():
    """Outlast keyword detection and +1/+1 counter."""
    card = make_creature('Monk', 1, 1, oracle='Outlast {1}{W}')
    assert has_outlast_card(card)
    monk = place_on_battlefield(card, 0, fresh_game().zones)
    outlast_detail = apply_outlast(monk)
    assert outlast_detail is not None
    assert monk.counters.get('+1/+1') == 1


def test_myriad_has_no_extra_targets_in_two_player_game():
    """Myriad keyword detection with no extra opponents in 1v1."""
    game = fresh_game()
    card = make_creature('Horde', 3, 3, oracle='Myriad')
    assert has_myriad_card(card)
    horde = place_on_battlefield(card, 0, game.zones, sick=False)
    myriad_detail = apply_myriad_on_attack(game, horde, defending_player_idx=1)
    assert myriad_detail is None
