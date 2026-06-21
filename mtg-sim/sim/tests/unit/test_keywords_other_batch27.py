"""Unit tests for reinforce and transmute (batch 27)."""

from __future__ import annotations

from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.reinforce import (
    apply_reinforce_etb,
    has_reinforce,
)
from engine.abilities.keywords.other.transmute import (
    apply_transmute,
    can_transmute,
    has_transmute,
)
from engine.core.game_object import CardObject
from tests.conftest import (
    fresh_game,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_reinforce_puts_counters_on_etb():
    """Reinforce grants +1/+1 counters on ETB (simplified)."""
    perm = place_on_battlefield(
        make_creature('Soldier', 2, 2, oracle='Reinforce 2 — {1}{W}'),
        0,
        fresh_game().zones,
    )
    assert has_reinforce(perm)
    detail = apply_reinforce_etb(perm)
    assert detail is not None
    assert perm.counters.get('+1/+1', 0) == 2


def test_reinforce_etb_hook_runs_from_registry():
    """Reinforce is wired through apply_etb_other_abilities."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Veteran', 3, 3, oracle='Reinforce 1 — {W}'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, perm)
    assert any('reinforce' in line for line in details)


def test_transmute_searches_library_once_per_turn():
    """Transmute puts the top library card into hand."""
    game = fresh_game()
    top = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_instant('Find', cmc=1),
    )
    game.zones.player_zones[0].library.insert(0, top)
    perm = place_on_battlefield(
        make_creature('Wizard', 2, 2, oracle='Transmute {1}{U}'),
        0,
        game.zones,
    )
    assert has_transmute(perm)
    assert can_transmute(perm, game, 0, 'main1')
    detail = apply_transmute(game, perm)
    assert detail is not None
    assert 'transmute' in detail
    assert len(game.zones.player_zones[0].hand) == 1
    assert not can_transmute(perm, game, 0, 'main1')
