"""Unit tests for casting batch 36: flashback, madness, suspend, plot, delve, convoke."""

from __future__ import annotations

from engine.abilities.keywords.casting.convoke import (
    has_convoke_card,
    resolve_convoke_for_cast,
)
from engine.abilities.keywords.casting.delve import (
    has_delve_card,
    resolve_delve_for_cast,
)
from engine.abilities.keywords.casting.flashback import (
    can_cast_via_flashback,
    flashback_mana_needed,
    has_flashback_card,
)
from engine.abilities.keywords.casting.madness import has_madness_card, madness_mana_needed
from engine.abilities.keywords.casting.plot import has_plot_card, is_plottable_sorcery
from engine.abilities.keywords.casting.suspend import (
    exile_for_suspend,
    has_suspend_card,
    suspend_time_counters,
)
from engine.core.game_object import CardObject
from tests.conftest import (
    add_to_hand,
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_flashback_keyword_parses_cost_and_timing():
    """Flashback card detection, mana cost, and instant-speed timing."""
    card = make_instant('Ray', oracle='Flashback {2}{R}\nDeal 4 damage.')
    assert has_flashback_card(card)
    assert flashback_mana_needed(card) == 3
    assert can_cast_via_flashback(card, 'attack', True)


def test_madness_keyword_parses_alternate_cost():
    """Madness card detection and alternate cost parsing."""
    card = make_instant('Blight', oracle='Madness {1}{B}\nDestroy target creature.')
    assert has_madness_card(card)
    assert madness_mana_needed(card) == (2, 0)


def test_suspend_keyword_exiles_with_time_counters():
    """Suspend card detection and exile setup with counters."""
    game = fresh_game()
    card = make_creature('Rift', 2, 2, oracle='Suspend 3—{1}{R}')
    assert has_suspend_card(card)
    assert suspend_time_counters(card) == 3
    add_to_hand(card, 0, game.zones)
    suspended = exile_for_suspend(game.zones, 0, 0, suspend_time_counters(card))
    assert suspended.exiled_cast_mode == 'suspend'
    assert suspended.suspend_time_counters == 3


def test_plot_keyword_requires_sorcery():
    """Plot card detection and sorcery restriction."""
    sorcery = make_card('Scheme', type_line='Sorcery', oracle='Plot')
    instant = make_instant('Trick', oracle='Plot')
    assert has_plot_card(sorcery)
    assert is_plottable_sorcery(sorcery)
    assert has_plot_card(instant)
    assert not is_plottable_sorcery(instant)


def test_delve_keyword_exiles_graveyard_cards_for_mana():
    """Delve card detection and graveyard exile during payment."""
    game = fresh_game()
    zones = game.zones
    zones.player_zones[0].graveyard.extend(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_creature(f'Gy{i}', 1, 1))
        for i in range(2)
    )
    spell = make_instant('Cruise', cmc=5, oracle='Draw three cards. Delve')
    assert has_delve_card(spell)
    mana_left, exiled_count, err = resolve_delve_for_cast(spell, 5, [0, 1], zones, 0)
    assert err is None
    assert mana_left == 3
    assert exiled_count == 2


def test_convoke_keyword_taps_creatures_for_mana():
    """Convoke card detection and creature tap payment."""
    game = fresh_game()
    spell = make_instant('Mob', cmc=4, oracle='Convoke\nDeal 4 damage.')
    assert has_convoke_card(spell)
    soldier = place_on_battlefield(make_creature('Soldier', 1, 1), 0, game.zones)
    mana_left, _tapped, err = resolve_convoke_for_cast(
        spell,
        4,
        [soldier.obj_id],
        game.zones,
        0,
    )
    assert err is None
    assert mana_left == 3
    assert soldier.tapped
