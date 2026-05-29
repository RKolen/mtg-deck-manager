"""Unit and game-loop tests for convoke, delve, improvise, and emerge (batch 15)."""

from __future__ import annotations

from engine.abilities.keywords.casting.convoke import (
    has_convoke,
    normalize_convoke_creature_ids,
    resolve_convoke_for_cast,
)
from engine.abilities.keywords.casting.delve import (
    has_delve,
    normalize_delve_graveyard_indices,
    resolve_delve_for_cast,
)
from engine.abilities.keywords.casting.emerge import (
    emerge_cost,
    emerge_mana_needed,
    emerge_sacrifice_error,
    has_emerge,
)
from engine.abilities.keywords.casting.improvise import (
    has_improvise,
    normalize_improvise_artifact_ids,
    resolve_improvise_for_cast,
)
from engine.core.game_object import CardObject
from engine.game import create_game
from engine.game.helpers import card_to_client
from tests.conftest import (
    cast_announce_options,
    fresh_game,
    make_artifact,
    make_creature,
    make_deck,
    make_instant,
    place_on_battlefield,
    put_lands_on_battlefield,
)


def test_card_to_client_cast_modifier_flags():
    """Hand cards expose convoke, delve, improvise, and emerge for the play UI."""
    convoke = card_to_client(0, make_instant('Justice', oracle='Deal 4 damage. Convoke'), 10)
    delve = card_to_client(0, make_instant('Cruise', oracle='Draw three cards. Delve'), 10)
    improvise = card_to_client(0, make_instant('Order', oracle='Draw a card. Improvise'), 10)
    emerge = card_to_client(
        0,
        make_creature('Wurm', 7, 7, oracle='Emerge {6}{G}\nTrample'),
        10,
    )
    assert convoke['hasConvoke'] is True
    assert convoke['hasDelve'] is False
    assert delve['hasDelve'] is True
    assert improvise['hasImprovise'] is True
    assert emerge['hasEmerge'] is True
    assert emerge['hasConvoke'] is False


def test_has_convoke_detects_keyword():
    """Convoke is detected on oracle text."""
    card = make_instant('Mob', oracle='Convoke\nDeal 4 damage.')
    assert has_convoke(card)
    assert not has_convoke(make_instant('Bolt', oracle='Deal 3 damage.'))


def test_resolve_convoke_taps_creatures_and_reduces_mana():
    """Each convoked creature taps and reduces generic mana by one."""
    game = fresh_game()
    spell = make_instant('Mob', cmc=4, oracle='Convoke\nDeal 4 damage.')
    creature_a = place_on_battlefield(make_creature('Soldier'), 0, game.zones)
    creature_b = place_on_battlefield(make_creature('Knight'), 0, game.zones)
    ids = [creature_a.obj_id, creature_b.obj_id]
    assert normalize_convoke_creature_ids(spell, ids) == ids
    mana_left, tapped, err = resolve_convoke_for_cast(spell, 4, ids, game.zones, 0)
    assert err is None
    assert mana_left == 2
    assert tapped == ids
    assert creature_a.tapped and creature_b.tapped


def test_has_delve_and_exiles_graveyard_cards():
    """Delve exiles graveyard cards and reduces generic mana by one each."""
    game = fresh_game()
    spell = make_instant('Dig', cmc=3, oracle='Delve\nDraw a card.')
    filler = CardObject(controller_idx=0, owner_idx=0, card_info=make_instant('Filler'))
    game.zones.player_zones[0].graveyard.extend([filler, filler])
    assert has_delve(spell)
    assert normalize_delve_graveyard_indices(spell, [0, 1]) == [0, 1]
    mana_left, exiled, err = resolve_delve_for_cast(spell, 3, [0, 1], game.zones, 0)
    assert err is None
    assert mana_left == 1
    assert exiled == 2
    assert len(game.zones.player_zones[0].graveyard) == 0
    assert len(game.zones.player_zones[0].exile) == 2


def test_resolve_improvise_taps_artifacts_and_reduces_mana():
    """Each improvised artifact taps and reduces generic mana by one."""
    game = fresh_game()
    spell = make_instant('Scheme', cmc=3, oracle='Improvise\nDraw a card.')
    relic = place_on_battlefield(
        make_artifact('Relic'),
        0,
        game.zones,
    )
    assert has_improvise(spell)
    ids = [relic.obj_id]
    assert normalize_improvise_artifact_ids(spell, ids) == ids
    mana_left, tapped, err = resolve_improvise_for_cast(spell, 3, ids, game.zones, 0)
    assert err is None
    assert mana_left == 2
    assert tapped == ids
    assert relic.tapped


def test_has_emerge_parses_cost_and_mana():
    """Emerge cost parses and replaces the creature's mana cost."""
    card = make_creature(
        'Wurm',
        cmc=7,
        oracle='Trample\nEmerge {2}{G}',
        mana_cost='{5}{G}{G}',
    )
    assert has_emerge(card)
    assert emerge_cost(card) is not None
    assert emerge_mana_needed(card)[0] == 3
    assert not has_emerge(make_instant('Bolt', oracle='Emerge {0}'))


def test_emerge_sacrifice_requires_creature():
    """Emerge rejects non-creature sacrifices unless artifact is allowed."""
    game = fresh_game()
    creature_card = make_creature('Wurm', oracle='Emerge {0}')
    artifact_card = make_creature(
        'Wurm',
        oracle='Emerge {0}\n(Sacrifice an artifact or creature.)',
    )
    host = place_on_battlefield(make_creature('Bear', 2, 2), 0, game.zones)
    relic = place_on_battlefield(make_artifact('Relic'), 0, game.zones)
    assert emerge_sacrifice_error(game.zones, 0, creature_card, True, []) is not None
    assert emerge_sacrifice_error(game.zones, 0, creature_card, True, [host.obj_id]) is None
    assert emerge_sacrifice_error(game.zones, 0, creature_card, True, [relic.obj_id]) is not None
    assert emerge_sacrifice_error(game.zones, 0, artifact_card, True, [relic.obj_id]) is None


def test_game_convoke_cast_taps_creatures_to_pay_mana():
    """Convoke lets a burn spell be paid with tapped creatures and fewer lands."""
    burn = make_instant(
        name='Mob Justice',
        cmc=4,
        mana_cost='',
        oracle='Mob Justice deals 4 damage to any target. Convoke',
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 2)
    soldier = place_on_battlefield(make_creature('Soldier', 1, 1), 0, game.state.zones)
    knight = place_on_battlefield(make_creature('Knight', 1, 1), 0, game.state.zones)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=burn),
    ]
    data = game.action_cast(
        0,
        target_player=1,
        cast_options=cast_announce_options(
            convoke_creature_ids=[soldier.obj_id, knight.obj_id],
        ),
    )
    assert 'error' not in data
    assert data['opponentLife'] == 16
    assert soldier.tapped
    assert knight.tapped
