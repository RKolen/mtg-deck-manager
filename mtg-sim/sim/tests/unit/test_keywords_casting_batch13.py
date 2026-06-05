"""Unit tests for suspend, foretell, plot, and madness (batch 13)."""

from __future__ import annotations

from engine.abilities.keywords.casting.delayed_exile_cast import _CastTiming
from engine.abilities.keywords.casting.foretell import (
    FORETELL_EXILE_MODE,
    can_cast_foretold,
    can_foretell_setup,
    has_foretell,
)
from engine.abilities.keywords.casting.madness import can_cast_via_madness, has_madness
from engine.abilities.keywords.casting.plot import (
    PLOT_EXILE_MODE,
    can_cast_plotted,
    can_plot_setup,
    is_plottable_sorcery,
)
from engine.abilities.keywords.casting.suspend import can_suspend, has_suspend
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_card, make_creature, make_instant


def test_suspend_foretell_plot_madness_timing():
    """Hand keywords are legal during an empty-stack main phase."""
    suspend_card = make_creature('Rift', 2, 2, oracle='Suspend 4—{1}{R}')
    foretell_card = make_instant('Glimmer', oracle='Foretell {1}{U}\nDraw a card.')
    plot_card = make_card('Scheme', type_line='Sorcery', oracle='Plot')
    madness_card = make_instant('Blight', oracle='Madness {1}{B}\nDestroy target creature.')
    assert has_suspend(suspend_card)
    assert can_suspend(suspend_card, 'main1', True)
    assert has_foretell(foretell_card)
    assert can_foretell_setup('main1', True)
    assert is_plottable_sorcery(plot_card)
    assert can_plot_setup('main1', True)
    assert has_madness(madness_card)
    assert can_cast_via_madness(madness_card, 'main1', True)


def test_exiled_foretell_and_plot_may_be_cast():
    """Foretold and plotted cards in exile may be cast in main phase."""
    game = fresh_game()
    foretell_card = make_instant('Glimmer', oracle='Foretell {1}{U}\nDraw a card.')
    plot_card = make_card('Scheme', type_line='Sorcery', oracle='Plot')
    foretold = CardObject(controller_idx=0, owner_idx=0, card_info=foretell_card)
    foretold.exiled_cast_mode = FORETELL_EXILE_MODE
    plotted = CardObject(controller_idx=0, owner_idx=0, card_info=plot_card)
    plotted.exiled_cast_mode = PLOT_EXILE_MODE
    game.zones.player_zones[0].exile.extend([foretold, plotted])
    assert can_cast_foretold(foretell_card, _CastTiming(phase='main1', stack_is_empty=True))
    assert can_cast_plotted(plot_card, _CastTiming(phase='main1', stack_is_empty=True))
