"""Unit tests for sneak, freerunning, madness, and suspend (Phase E casting batch)."""

from __future__ import annotations

from engine.abilities.keywords.casting import (
    SneakCastInput,
    can_cast_via_madness,
    exile_for_suspend,
    freerunning_mana_needed,
    has_freerunning,
    has_madness,
    has_sneak,
    has_suspend,
    madness_mana_needed,
    normalize_freerunning_cast,
    normalize_sneak_land_hand_indices,
    resolve_sneak_for_cast,
    suspend_time_counters,
    tick_suspend_counters,
)
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_instant, make_land


def test_sneak_exiles_lands_and_reduces_mana():
    """Sneak exiles lands from hand to reduce generic mana owed."""
    spell = make_instant(
        'Bolt',
        cmc=2,
        mana_cost='{1}{R}',
        oracle='Sneak\nBolt deals 3 damage.',
    )
    land = make_land()
    game = fresh_game()
    game.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=spell),
        CardObject(controller_idx=0, owner_idx=0, card_info=land),
    ]
    assert has_sneak(spell)
    indices = normalize_sneak_land_hand_indices(spell, 0, [1])
    assert indices == [1]
    mana, exiled, err = resolve_sneak_for_cast(
        spell,
        2,
        game.zones,
        0,
        SneakCastInput(0, tuple(indices)),
    )
    assert err is None
    assert mana == 0
    assert exiled == 1
    assert len(game.zones.player_zones[0].exile) == 1


def test_freerunning_requires_combat_damage_flag():
    """Freerunning alternate cost applies only after combat damage was dealt."""
    card = make_instant(
        'Slither',
        oracle='Freerunning {B}\nSlither deals 2 damage to any target.',
        mana_cost='{2}{B}',
    )
    assert has_freerunning(card)
    assert freerunning_mana_needed(card) == (1, 0)
    assert not normalize_freerunning_cast(card, True, False)
    assert normalize_freerunning_cast(card, True, True)


def test_madness_parses_alternate_cost():
    """Madness cost is parsed and castable at instant speed."""
    card = make_instant(
        'Fiery Temper',
        oracle='Madness {R}\nFiery Temper deals 3 damage to any target.',
    )
    assert has_madness(card)
    assert madness_mana_needed(card) == (1, 0)
    assert can_cast_via_madness(card, 'attack', False)


def test_suspend_counters_tick_to_ready():
    """Suspended cards lose a counter each upkeep and become ready at zero."""
    card = make_instant('Rage', oracle='Suspend 1—{R}\nDraw a card.')
    game = fresh_game()
    game.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=card),
    ]
    assert has_suspend(card)
    assert suspend_time_counters(card) == 1
    exiled = exile_for_suspend(game.zones, 0, 0, 1)
    assert exiled.suspend_time_counters == 1
    ready = tick_suspend_counters(game.zones, 0)
    assert len(ready) == 1
    assert exiled.suspend_time_counters == 0
