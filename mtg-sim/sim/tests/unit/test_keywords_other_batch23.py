"""Unit tests for fading, cumulative upkeep, and melee (batch 23)."""

from __future__ import annotations

from engine.abilities.keywords.other.cumulative_upkeep import (
    apply_cumulative_upkeep_etb,
    has_cumulative_upkeep,
    resolve_cumulative_upkeep,
)
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.fading import (
    apply_fading_etb,
    has_fading,
    resolve_fading_upkeep,
)
from engine.abilities.keywords.other.melee import apply_melee_on_mass_attack, has_melee
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_fading_etb_puts_counters():
    """Fading enters with fade counters."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Ith', 2, 2, oracle='Fading 3'),
        0,
        game.zones,
    )
    assert has_fading(perm)
    detail = apply_fading_etb(perm)
    assert detail is not None
    assert perm.counters.get('fade', 0) == 3


def test_fading_upkeep_removes_counters_and_sacrifices():
    """Fading sacrifices the permanent when fade counters reach zero."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Spark', 1, 1, oracle='Fading 1'),
        0,
        game.zones,
    )
    apply_fading_etb(perm)
    details = resolve_fading_upkeep(game, 0)
    assert any('sacrificed' in line for line in details)
    assert len(game.zones.battlefield) == 0


def test_cumulative_upkeep_etb_and_pay():
    """Cumulative upkeep can be paid at upkeep."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Taxer', 2, 2, oracle='Cumulative upkeep {1}'),
        0,
        game.zones,
    )
    assert has_cumulative_upkeep(perm)
    apply_cumulative_upkeep_etb(perm)
    paid: list[bool] = []

    def tap_mana(_player_idx: int, _amount: int) -> bool:
        paid.append(True)
        return True

    details = resolve_cumulative_upkeep(game, 0, tap_mana)
    assert paid
    assert any('paid cumulative upkeep' in line for line in details)
    assert len(game.zones.battlefield) == 1


def test_fading_etb_hook_runs_from_registry():
    """Fading is wired through apply_etb_other_abilities."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Fade', 2, 2, oracle='Fading 2'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, perm)
    assert any('fading' in line for line in details)


def test_melee_triggers_on_mass_attack():
    """Melee bonuses apply when three or more creatures attack."""
    game = fresh_game()
    place_on_battlefield(
        make_creature('Captain', 3, 3, oracle='Melee — Whenever you attack, draw a card.'),
        0,
        game.zones,
    )
    assert has_melee(game.zones.battlefield[0])
    details = apply_melee_on_mass_attack(game, 0, 3)
    assert details
    assert any('melee' in line for line in details)


def test_melee_ignored_with_few_attackers():
    """Melee does nothing when fewer than three creatures attack."""
    game = fresh_game()
    place_on_battlefield(
        make_creature('Scout', 1, 1, oracle='Melee'),
        0,
        game.zones,
    )
    assert not apply_melee_on_mass_attack(game, 0, 2)
