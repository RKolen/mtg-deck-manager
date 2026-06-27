"""Unit tests for batch 42 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.other.blitz import (
    apply_blitz_etb,
    has_blitz_card,
    sacrifice_blitz_creatures,
)
from engine.abilities.keywords.other.dash import apply_dash_etb, has_dash_card
from engine.abilities.keywords.other.disguise import (
    apply_turn_up_disguise,
    has_disguise_card,
    normalize_disguise_cast,
)
from engine.abilities.keywords.other.embalm import apply_embalm_etb, has_embalm_card
from engine.abilities.keywords.other.evoke import (
    apply_evoke_on_etb,
    has_evoke_card,
    mark_evoked_cast,
)
from engine.abilities.keywords.other.forecast import can_forecast, has_forecast_card
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_blitz_keyword_haste_and_eot_sacrifice():
    """Blitz card detection, haste on ETB, and sacrifice at end of turn."""
    game = fresh_game()
    card = make_creature('Racer', 2, 1, oracle='Blitz {1}{R}')
    assert has_blitz_card(card)
    racer = place_on_battlefield(card, 0, game.zones)
    racer.counters['blitz'] = 1
    racer.sick = True
    blitz_detail = apply_blitz_etb(racer)
    assert blitz_detail is not None
    assert not racer.sick
    sacrifice_lines = sacrifice_blitz_creatures(game, 0)
    assert sacrifice_lines
    assert racer not in game.zones.battlefield


def test_dash_keyword_grants_haste_when_dashed():
    """Dash card detection and haste when cast for dash."""
    card = make_creature('Sprinter', 3, 2, oracle='Dash {2}{R}')
    assert has_dash_card(card)
    sprinter = place_on_battlefield(card, 0, fresh_game().zones)
    sprinter.counters['dash'] = 1
    sprinter.sick = True
    dash_detail = apply_dash_etb(sprinter)
    assert dash_detail is not None
    assert not sprinter.sick


def test_disguise_keyword_supports_face_down_cast():
    """Disguise card detection and face-up turn."""
    card = make_creature('Agent', 2, 3, oracle='Disguise {1}{U}')
    assert has_disguise_card(card)
    assert normalize_disguise_cast(card, cast_for_disguise=True)
    agent = place_on_battlefield(card, 0, fresh_game().zones)
    agent.face_down = True
    disguise_detail = apply_turn_up_disguise(agent)
    assert disguise_detail is not None
    assert not agent.face_down


def test_embalm_keyword_creates_exile_token_on_etb():
    """Embalm card detection and zombie token in exile."""
    game = fresh_game()
    card = make_creature('Honored', 4, 4, oracle='Embalm {4}{W}')
    assert has_embalm_card(card)
    honored = place_on_battlefield(card, 0, game.zones)
    embalm_detail = apply_embalm_etb(game.zones, honored)
    assert embalm_detail is not None
    assert len(game.zones.player_zones[0].exile) >= 1


def test_evoke_keyword_sacrifices_on_etb():
    """Evoke card detection and sacrifice when cast for evoke."""
    game = fresh_game()
    card = make_creature('Elemental', 4, 4, oracle='Evoke {2}{U}')
    assert has_evoke_card(card)
    elemental = place_on_battlefield(card, 0, game.zones)
    mark_evoked_cast(elemental)
    evoke_detail = apply_evoke_on_etb(game, elemental)
    assert evoke_detail is not None
    assert elemental not in game.zones.battlefield


def test_forecast_keyword_available_on_draw_step():
    """Forecast card detection and draw-step activation window."""
    card = make_instant('Gelid', oracle='Forecast — Draw a card.')
    assert has_forecast_card(card)
    assert can_forecast(card, 'draw', True)
    assert not can_forecast(card, 'main1', True)
