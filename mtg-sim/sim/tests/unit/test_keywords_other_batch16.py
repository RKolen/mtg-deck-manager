"""Unit and game-loop tests for harmonize, spectacle, and morph (batch 16)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaModifiers,
    CastManaTiming,
    _TimingAvailability,
    resolve_announce_cast_mana,
)
from engine.game.face_alternate_cast import FaceAlternateCastFlags
from engine.abilities.keywords.casting.harmonize import (
    harmonize_cost,
    harmonize_mana_needed,
    harmonize_tap_error,
    has_harmonize,
    resolve_harmonize_mana,
)
from engine.abilities.keywords.casting.spectacle import (
    has_spectacle,
    normalize_spectacle_cast,
    spectacle_available,
    spectacle_mana_needed,
)
from engine.abilities.keywords.other.morph import (
    apply_turn_up_morph,
    can_turn_up_morph,
    has_megamorph,
    has_morph,
    morph_face_down_mana_needed,
    morph_turn_up_mana_needed,
    normalize_morph_cast,
)
from engine.core.game_object import (
    CardObject,
    SpellAlternateCast,
    SpellOnStack,
    spell_exiles_from_graveyard_cast,
    _GraveyardAlts,
    _SpellCasting,
)
from engine.game import create_game
from engine.game.helpers import HandCastContext, card_to_client
from tests.conftest import (
    fresh_game,
    make_artifact,
    make_creature,
    make_deck,
    make_instant,
    place_on_battlefield,
    put_lands_on_battlefield,
)


def test_spectacle_requires_opponent_lost_life():
    """Spectacle is only legal when an opponent was dealt damage this turn."""
    game = fresh_game()
    card = make_instant('Rix', oracle='Spectacle {R}\nDeal 3 damage.')
    assert has_spectacle(card)
    assert not spectacle_available(game, 0)
    game.players[1].was_dealt_damage_this_turn = True
    assert spectacle_available(game, 0)
    assert normalize_spectacle_cast(
        card,
        True,
        available=spectacle_available(game, 0),
    )


def test_harmonize_tap_reduces_generic_mana():
    """Tapping a creature for harmonize reduces the generic portion of the cost."""
    game = fresh_game()
    zones = game.zones
    card = make_instant('Song', oracle='Harmonize {4}{U}\nDraw two cards.')
    assert has_harmonize(card)
    helper = place_on_battlefield(make_creature('Bard', 3, 3), 0, zones, sick=False)
    mana, life, err = resolve_harmonize_mana(card, zones, 0, helper.obj_id)
    assert err is None
    assert life == 0
    assert mana == harmonize_mana_needed(card)[0] - 3
    assert helper.tapped


def test_morph_face_down_and_megamorph_turn_up():
    """Morph casts as 2/2 face down; megamorph adds a counter when turned up."""
    game = fresh_game()
    card = make_creature('Sagu', 5, 5, oracle='Megamorph {3}{G}\nTrample')
    assert has_morph(card)
    assert has_megamorph(card)
    assert normalize_morph_cast(card, True)
    assert morph_face_down_mana_needed() == (3, 0)
    perm = place_on_battlefield(card, 0, game.zones)
    perm.face_down = True
    detail = apply_turn_up_morph(perm)
    assert detail
    assert not perm.face_down
    assert perm.counters.get('+1/+1') == 1


def test_card_to_client_spectacle_and_morph_flags():
    """Hand cards expose spectacle and morph for the play UI."""
    game = fresh_game()
    game.players[1].was_dealt_damage_this_turn = True
    ctx = HandCastContext(game=game, controller_idx=0)
    spec = card_to_client(
        0,
        make_instant('Show', oracle='Spectacle {1}{R}\nDeal 2.'),
        10,
        ctx,
    )
    morph_card = card_to_client(
        0,
        make_creature('Shifter', 4, 4, oracle='Morph {2}{G}'),
        10,
        ctx,
    )
    assert spec['hasSpectacle'] is True
    assert spec['spectacleAvailable'] is True
    assert morph_card['hasMorph'] is True


def test_has_harmonize_parses_cost():
    """Harmonize cost parses from oracle text."""
    card = make_instant('Tune', oracle='Harmonize {2}{B}\nDraw a card.')
    assert has_harmonize(card)
    assert harmonize_cost(card) is not None
    assert harmonize_mana_needed(card)[0] == 3
    assert not has_harmonize(make_instant('Bolt', oracle='Deal 3 damage.'))


def test_harmonize_tap_error_rejects_illegal_creature():
    """Harmonize tap validation rejects tapped or non-creature permanents."""
    harmonize_spell = make_instant('Song', oracle='Harmonize {1}{U}\nDraw a card.')
    assert has_harmonize(harmonize_spell)
    game = fresh_game()
    helper = place_on_battlefield(make_creature('Bard', 2, 2), 0, game.zones, sick=False)
    relic = place_on_battlefield(make_artifact('Relic'), 0, game.zones)
    assert harmonize_tap_error(game.zones, 0, None) is None
    assert harmonize_tap_error(game.zones, 0, helper.obj_id) is None
    helper.tapped = True
    assert harmonize_tap_error(game.zones, 0, helper.obj_id) is not None
    assert harmonize_tap_error(game.zones, 0, relic.obj_id) is not None


def test_spectacle_and_morph_announce_mana():
    """Spectacle and morph face-down use their alternate mana costs."""
    spec_card = make_instant('Show', oracle='Spectacle {1}{R}\nDeal 2.')
    morph_card = make_creature('Shifter', 4, 4, oracle='Morph {2}{G}')
    spec_mana, _ = resolve_announce_cast_mana(
        spec_card,
        AnnounceCastManaOptions(
            timing=CastManaTiming(
                cast_for_spectacle=True,
                available=_TimingAvailability(spectacle_available=True),
            ),
        ),
    )
    morph_mana, _ = resolve_announce_cast_mana(
        morph_card,
        AnnounceCastManaOptions(
            modifiers=CastManaModifiers(
                face=FaceAlternateCastFlags(cast_for_morph=True),
            ),
        ),
    )
    assert spec_mana == spectacle_mana_needed(spec_card)[0]
    assert morph_mana == morph_face_down_mana_needed()[0]


def test_game_harmonize_and_turn_up_morph():
    """Harmonize casts from the graveyard and exiles; morph can turn face up."""
    song = make_instant(
        name='Winternight',
        cmc=4,
        oracle='Draw two cards.\nHarmonize {2}{U}',
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 3)
    gy_card = CardObject(controller_idx=0, owner_idx=0, card_info=song)
    game.state.zones.player_zones[0].graveyard.append(gy_card)
    cast = game.action_cast_harmonize(0)
    assert 'error' not in cast
    spell = SpellOnStack(
        controller_idx=0,
        owner_idx=0,
        source=gy_card,
        casting=_SpellCasting(alternate=SpellAlternateCast(
            graveyard=_GraveyardAlts(harmonize=True)
        ),),
    )
    assert spell_exiles_from_graveyard_cast(spell)

    shifter_info = make_creature('Shifter', 4, 4, oracle='Morph {2}{G}')
    face_down = place_on_battlefield(shifter_info, 0, game.state.zones)
    face_down.face_down = True
    assert can_turn_up_morph(face_down, game.state, 0, 'main1')
    put_lands_on_battlefield(game, 5)
    turn_up = game.action_turn_up_morph(str(face_down.obj_id))
    assert 'error' not in turn_up
    assert not face_down.face_down
    assert morph_turn_up_mana_needed(shifter_info) == 3
