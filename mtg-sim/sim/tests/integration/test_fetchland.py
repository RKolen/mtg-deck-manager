"""Integration tests for fetchland activated abilities."""

from __future__ import annotations

from engine.core.game_object import CardObject
from tests.conftest import create_game, make_card, make_deck, make_land

_SCALDING_TARN_ORACLE = (
    '{T}, Pay 1 life, Sacrifice Scalding Tarn: '
    'Search your library for an Island or Mountain card, '
    'put it onto the battlefield, then shuffle.'
)


def test_fetchland_activation_puts_matching_land_from_library():
    """Activating a fetchland opens search; choosing a land completes the fetch."""
    tarn = make_card(
        name='Scalding Tarn',
        type_line='Land',
        oracle=_SCALDING_TARN_ORACLE,
    )
    game = create_game([tarn], make_deck(lands=20))
    game.action_keep()
    hand = game.state.zones.player_zones[0].hand
    tarn_idx = next(
        idx for idx, card in enumerate(hand)
        if isinstance(card, CardObject)
        and card.card_info is not None
        and card.card_info.name == 'Scalding Tarn'
    )
    game.action_play_land(tarn_idx)
    island = make_land('Island', 'U')
    game.state.zones.player_zones[0].library.insert(
        0,
        CardObject(controller_idx=0, owner_idx=0, card_info=island),
    )
    tarn_perm = game.state.zones.battlefield[0]
    data = game.action_activate(str(tarn_perm.obj_id), 0)
    assert data['fetchSearch'] is not None
    assert 'Island' in data['fetchSearch']['fetchableNames']
    island_entry = next(
        entry for entry in data['playerLibrary'] if entry['name'] == 'Island'
    )
    data = game.action_fetch_land(island_entry['libraryIdx'])
    names = [perm['name'] for perm in data['playerBattlefield']]
    assert 'Island' in names
    assert 'Scalding Tarn' not in names
    assert data['playerLife'] == 19


def test_fetchland_matches_dual_land_via_produced_mana():
    """Shocklands without subtype text still match when produced_mana is set."""
    tarn = make_card(
        name='Scalding Tarn',
        type_line='Land',
        oracle=_SCALDING_TARN_ORACLE,
    )
    steam_vents = make_card(
        name='Steam Vents',
        type_line='Land',
        oracle='({T}: Add {U} or {R}.)',
        mana_cost='',
    )
    steam_vents.mana.produced = ['U', 'R']
    game = create_game([tarn], make_deck(lands=0))
    game.action_keep()
    hand = game.state.zones.player_zones[0].hand
    tarn_idx = next(
        idx for idx, card in enumerate(hand)
        if isinstance(card, CardObject)
        and card.card_info is not None
        and card.card_info.name == 'Scalding Tarn'
    )
    game.action_play_land(tarn_idx)
    game.state.zones.player_zones[0].library.insert(
        0,
        CardObject(controller_idx=0, owner_idx=0, card_info=steam_vents),
    )
    tarn_perm = game.state.zones.battlefield[0]
    data = game.action_activate(str(tarn_perm.obj_id), 0)
    option_names = data['fetchSearch']['fetchableNames']
    assert 'Steam Vents' in option_names
