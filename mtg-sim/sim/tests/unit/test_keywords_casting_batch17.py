"""Unit and game-loop tests for sneak, freerunning, dash, and blitz (batch 17)."""

from __future__ import annotations

from engine.abilities.keywords.casting.blitz import (
    blitz_mana_needed,
    has_blitz,
    normalize_blitz_cast,
)
from engine.abilities.keywords.casting.dash import (
    dash_mana_needed,
    has_dash,
    normalize_dash_cast,
)
from engine.abilities.keywords.casting.freerunning import (
    freerunning_mana_needed,
    has_freerunning,
    normalize_freerunning_cast,
)
from engine.abilities.keywords.casting.sneak import (
    has_sneak,
    resolve_sneak_for_cast,
    SneakCastInput,
)
from engine.core.game_object import CardObject
from engine.game import create_game
from engine.game.helpers import card_to_client, HandCastContext
from tests.conftest import (
    _CardStats,
    cast_announce_options,
    fresh_game,
    make_card,
    make_creature,
    make_deck,
    make_instant,
    make_land,
    put_lands_on_battlefield,
)


def test_has_sneak_detects_keyword():
    """Sneak is detected on oracle text."""
    card = make_instant('Thief', oracle='Sneak\nDraw a card.')
    assert has_sneak(card)
    assert not has_sneak(make_instant('Bolt', oracle='Deal 3 damage.'))


def test_sneak_exiles_land_and_reduces_mana():
    """Each exiled land reduces generic mana by two."""
    game = fresh_game()
    spell = make_instant('Thief', cmc=4, oracle='Sneak\nDraw two cards.')
    land = CardObject(controller_idx=0, owner_idx=0, card_info=make_land('Forest'))
    game.zones.player_zones[0].hand.extend([
        CardObject(controller_idx=0, owner_idx=0, card_info=spell),
        land,
    ])
    mana, exiled, err = resolve_sneak_for_cast(
        spell,
        4,
        game.zones,
        0,
        SneakCastInput(spell_hand_idx=0, land_hand_indices=(1,)),
    )
    assert err is None
    assert mana == 2
    assert exiled == 1
    assert len(game.zones.player_zones[0].exile) == 1


def test_freerunning_requires_combat_damage():
    """Freerunning is only available after dealing combat damage."""
    card = make_instant('Slither', oracle='Freerunning {0}\nDeal 2 damage.')
    assert has_freerunning(card)
    assert not normalize_freerunning_cast(card, True, False)
    assert normalize_freerunning_cast(card, True, True)
    assert freerunning_mana_needed(card)[0] == 0


def test_dash_and_blitz_parse_alt_costs():
    """Dash and blitz expose alternate costs for creatures."""
    dasher = make_creature('Sprinter', 3, 3, oracle='Dash {1}{R}')
    blitzer = make_creature('Blitzer', 2, 2, oracle='Blitz {1}{R}')
    assert has_dash(dasher)
    assert normalize_dash_cast(dasher, True)
    assert dash_mana_needed(dasher)[0] == 2
    assert has_blitz(blitzer)
    assert normalize_blitz_cast(blitzer, True)
    assert blitz_mana_needed(blitzer)[0] == 2


def test_card_to_client_sneak_dash_blitz_flags():
    """Hand cards expose sneak, dash, blitz, and freerunning for the play UI."""
    game = fresh_game()
    game.players[0].combat_damage_dealt_this_turn = True
    ctx = HandCastContext(game=game, controller_idx=0)
    sneak_card = card_to_client(0, make_instant('Sneak', oracle='Sneak\nDraw.'), 10, ctx)
    dash_card = card_to_client(
        0,
        make_creature('Racer', 3, 3, oracle='Dash {1}{R}'),
        10,
        ctx,
    )
    assert sneak_card['hasSneak'] is True
    assert dash_card['hasDash'] is True
    assert dash_card['freerunningAvailable'] is False


def test_game_sneak_cast_exiles_land():
    """Sneak cast from hand exiles a land and reduces the spell cost."""
    bolt = make_instant(
        name='Bolt',
        cmc=2,
        mana_cost='{1}{R}',
        oracle='Sneak\nBolt deals 2 damage to any target.',
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=bolt),
        CardObject(controller_idx=0, owner_idx=0, card_info=make_land()),
    ]
    data = game.action_cast(
        0,
        target_player=1,
        cast_options=cast_announce_options(sneak_land_hand_indices=[1]),
    )
    assert 'error' not in data
    assert len(game.state.zones.player_zones[0].exile) == 1


def test_game_dash_cast_marks_creature():
    """Casting for dash marks the creature for end-of-turn return."""
    sprinter = make_card(
        name='Sprinter',
        type_line='Creature — Human Warrior',
        oracle='Dash {1}{R}\nHaste',
        stats=_CardStats(cmc=3.0, pt='2/1'),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 2)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=sprinter),
    ]
    data = game.action_cast(
        0,
        cast_options=cast_announce_options(cast_for_dash=True),
    )
    assert 'error' not in data
    perm = next(p for p in game.state.zones.battlefield if p.name == 'Sprinter')
    assert perm.counters.get('dash') == 1
    assert not perm.sick


def test_game_blitz_cast_marks_creature():
    """Casting for blitz marks the creature for end-of-turn sacrifice."""
    blitzer = make_card(
        name='Blitzer',
        type_line='Creature — Human Warrior',
        oracle='Blitz {1}{R}',
        stats=_CardStats(cmc=2.0, pt='2/1'),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 2)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=blitzer),
    ]
    data = game.action_cast(
        0,
        cast_options=cast_announce_options(cast_for_blitz=True),
    )
    assert 'error' not in data
    perm = next(p for p in game.state.zones.battlefield if p.name == 'Blitzer')
    assert perm.counters.get('blitz') == 1
