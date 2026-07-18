"""Tests for shockland enter-the-battlefield choices."""

from __future__ import annotations

from engine.core.game_object import CardObject
from tests.conftest import create_game, make_card, make_deck

_STEAM_VENTS_ORACLE = (
    'As Steam Vents enters the battlefield, you may pay 2 life. '
    "If you don't, it enters the battlefield tapped.\n"
    '({T}: Add {U} or {R}.)'
)


def test_shockland_enters_tapped_by_default():
    """Shocklands enter tapped unless the player pays 2 life."""
    steam_vents = make_card(
        name='Steam Vents',
        type_line='Land — Island Mountain',
        oracle=_STEAM_VENTS_ORACLE,
        mana_cost='',
    )
    steam_vents.mana.produced = ['U', 'R']
    game = create_game([steam_vents], make_deck(lands=20))
    game.action_keep()
    hand = game.state.zones.player_zones[0].hand
    idx = next(
        i for i, card in enumerate(hand)
        if isinstance(card, CardObject)
        and card.card_info is not None
        and card.card_info.name == 'Steam Vents'
    )
    data = game.action_play_land(idx, pay_shockland_life=False)
    perm = data['playerBattlefield'][0]
    assert perm['name'] == 'Steam Vents'
    assert perm['tapped'] is True
    assert data['playerLife'] == 20


def test_shockland_can_pay_life_to_enter_untapped():
    """Shocklands can enter untapped when the player pays 2 life."""
    steam_vents = make_card(
        name='Steam Vents',
        type_line='Land — Island Mountain',
        oracle=_STEAM_VENTS_ORACLE,
        mana_cost='',
    )
    steam_vents.mana.produced = ['U', 'R']
    game = create_game([steam_vents], make_deck(lands=20))
    game.action_keep()
    hand = game.state.zones.player_zones[0].hand
    idx = next(
        i for i, card in enumerate(hand)
        if isinstance(card, CardObject)
        and card.card_info is not None
        and card.card_info.name == 'Steam Vents'
    )
    data = game.action_play_land(idx, pay_shockland_life=True)
    perm = data['playerBattlefield'][0]
    assert perm['name'] == 'Steam Vents'
    assert perm['tapped'] is False
    assert data['playerLife'] == 18
