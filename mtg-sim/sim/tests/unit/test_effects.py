"""Unit tests for engine/cards/effects.py and script_loader.py (Phase G)."""

from engine.cards.effects import (
    CardEffectContext,
    ConditionalEffect,
    DealDamageToPlayer,
    DrawCards,
    EffectList,
    GainLife,
    LoseLife,
    Mill,
    Scry,
)
from engine.cards.script_loader import has_script, resolve_scripted_spell
from engine.core.game_object import CardObject
from tests.conftest import add_to_library, fresh_game, make_card, make_instant


def _card(name: str, oracle: str = '') -> CardObject:
    return CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_card(name=name, type_line='Sorcery', oracle=oracle),
    )


def _ctx(game, *, target_player_idx: int | None = None) -> CardEffectContext:
    return CardEffectContext(
        game=game,
        controller_idx=0,
        source=_card('Test'),
        target_player_idx=target_player_idx,
    )


def test_mill_moves_library_cards_to_graveyard():
    """Mill sends the top cards of the opponent's library to the graveyard."""
    game = fresh_game()
    for idx in range(3):
        add_to_library(make_instant(f'C{idx}'), 1, game.zones)
    detail = Mill(count=2, target='opponent').apply(_ctx(game))
    assert 'milled 2' in detail
    assert len(game.zones.player_zones[1].graveyard) == 2


def test_mill_each_player():
    """Mill with target each hits both libraries."""
    game = fresh_game()
    add_to_library(make_instant('A'), 0, game.zones)
    add_to_library(make_instant('B'), 1, game.zones)
    detail = Mill(count=1, target='each').apply(_ctx(game))
    assert 'P1 milled 1' in detail
    assert 'P2 milled 1' in detail


def test_draw_cards_uses_zones_draw():
    """DrawCards moves cards from library to hand."""
    game = fresh_game()
    add_to_library(make_instant('Drawn'), 0, game.zones)
    detail = DrawCards(count=1).apply(_ctx(game))
    assert detail == 'drew 1 card(s)'
    assert len(game.zones.player_zones[0].hand) == 1


def test_gain_and_lose_life():
    """GainLife and LoseLife adjust the controller's life total."""
    game = fresh_game()
    assert GainLife(amount=3).apply(_ctx(game)) == 'gained 3 life'
    assert game.players[0].life == 23
    assert LoseLife(amount=2).apply(_ctx(game)) == 'lost 2 life'
    assert game.players[0].life == 21


def test_deal_damage_to_player():
    """DealDamageToPlayer reduces the opponent's life."""
    game = fresh_game()
    detail = DealDamageToPlayer(amount=4, target='opponent').apply(_ctx(game))
    assert detail == 'dealt 4 to P2'
    assert game.players[1].life == 16


def test_scry_puts_cards_on_bottom():
    """Scry reorders the top of the library."""
    game = fresh_game()
    add_to_library(make_instant('Top'), 0, game.zones)
    add_to_library(make_instant('Second'), 0, game.zones)
    detail = Scry(count=2, bottom_indices=(0,)).apply(_ctx(game))
    assert 'scry 2' in detail
    lib = game.zones.player_zones[0].library
    top = lib[0]
    assert isinstance(top, CardObject)
    assert top.card_info is not None
    assert top.card_info.name == 'Second'


def test_effect_list_applies_in_order():
    """EffectList runs child effects sequentially."""
    game = fresh_game()
    add_to_library(make_instant('Top'), 0, game.zones)
    detail = EffectList((
        GainLife(amount=2),
        DrawCards(count=1),
    )).apply(_ctx(game))
    assert 'gained 2 life' in detail
    assert 'drew 1 card(s)' in detail
    assert game.players[0].life == 22


def test_conditional_effect_branches():
    """ConditionalEffect picks when_true or when_false."""
    game = fresh_game()
    true_effect = ConditionalEffect(
        condition=lambda ctx: ctx.controller_idx == 0,
        when_true=GainLife(amount=1),
        when_false=LoseLife(amount=1),
    )
    assert 'gained 1 life' in true_effect.apply(_ctx(game))
    false_effect = ConditionalEffect(
        condition=lambda ctx: ctx.controller_idx == 1,
        when_true=GainLife(amount=5),
        when_false=GainLife(amount=1),
    )
    assert 'gained 1 life' in false_effect.apply(_ctx(game))


def test_script_loader_mind_funeral_mills_target_player():
    """Mind Funeral script mills four via script_loader."""
    game = fresh_game()
    for idx in range(4):
        add_to_library(make_instant(f'G{idx}'), 1, game.zones)
    source = _card('Mind Funeral', oracle='Target player mills four cards.')
    ctx = CardEffectContext(
        game=game,
        controller_idx=0,
        source=source,
        target_player_idx=1,
    )
    assert source.card_info is not None
    assert has_script(source.card_info) is True
    detail = resolve_scripted_spell(ctx)
    assert detail is not None
    assert 'milled 4' in detail
    assert len(game.zones.player_zones[1].graveyard) == 4


def test_script_loader_returns_none_for_unscripted_card():
    """Unscripted cards return None so regex handlers can run."""
    game = fresh_game()
    source = _card('Random Spell')
    ctx = CardEffectContext(game=game, controller_idx=0, source=source)
    assert resolve_scripted_spell(ctx) is None
