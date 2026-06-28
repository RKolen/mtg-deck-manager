"""Unit tests for casting batch 37: cascade, storm, foretell, emerge, improvise, sneak."""

from __future__ import annotations

from engine.abilities.keywords.casting.cascade import (
    has_cascade_card,
    reveal_cascade_hit,
)
from engine.abilities.keywords.casting.emerge import emerge_mana_needed, has_emerge_card
from engine.abilities.keywords.casting.foretell import (
    can_foretell_setup,
    has_foretell_card,
)
from engine.abilities.keywords.casting.improvise import (
    has_improvise_card,
    resolve_improvise_for_cast,
)
from engine.abilities.keywords.casting.sneak import (
    SneakCastInput,
    has_sneak_card,
    resolve_sneak_for_cast,
)
from engine.abilities.keywords.casting.storm import (
    has_storm_card,
    storm_copy_count,
    supports_storm_copies,
)
from engine.core.game_object import CardObject, ZoneCard
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_artifact,
    make_card,
    make_creature,
    make_instant,
    make_land,
    place_on_battlefield,
)


def test_cascade_keyword_finds_lower_cmc_spell():
    """Cascade card detection and library reveal for a lower mana value."""
    card = make_creature('Bloodbraid', 4, 4, oracle='Cascade')
    assert has_cascade_card(card)
    library: list[ZoneCard] = [
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_card('Land', type_line='Basic Land — Island', stats=_CardStats(cmc=0.0)),
        ),
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_instant('Bolt', cmc=1.0, mana_cost='{R}'),
        ),
    ]
    reveal = reveal_cascade_hit(library, max_mana_value=4)
    assert reveal.hit is not None
    assert reveal.hit.card_info is not None
    assert reveal.hit.card_info.name == 'Bolt'


def test_storm_keyword_counts_spell_copies():
    """Storm card detection and copy count from spells cast this turn."""
    card = make_instant('Flames', oracle='Storm\nDeal 1 damage.')
    assert has_storm_card(card)
    assert supports_storm_copies(card)
    assert storm_copy_count(4) == 3


def test_foretell_keyword_available_in_main_phase():
    """Foretell card detection and setup timing."""
    card = make_instant('Glimmer', oracle='Foretell {1}{U}\nDraw a card.')
    assert has_foretell_card(card)
    assert can_foretell_setup('main1', True)
    assert not can_foretell_setup('attack', True)


def test_emerge_keyword_parses_creature_cost():
    """Emerge card detection and alternate cost on creatures."""
    card = make_creature('Wurm', 7, 7, oracle='Emerge {6}{G}\nTrample')
    assert has_emerge_card(card)
    assert emerge_mana_needed(card) == (7, 0)


def test_improvise_keyword_taps_artifacts_for_mana():
    """Improvise card detection and artifact tap payment."""
    game = fresh_game()
    spell = make_instant('Order', cmc=3, oracle='Draw a card. Improvise')
    assert has_improvise_card(spell)
    relic = place_on_battlefield(make_artifact('Relic'), 0, game.zones)
    mana_left, _tapped, err = resolve_improvise_for_cast(
        spell,
        3,
        [relic.obj_id],
        game.zones,
        0,
    )
    assert err is None
    assert mana_left == 2
    assert relic.tapped


def test_sneak_keyword_exiles_lands_for_discount():
    """Sneak card detection and land exile mana reduction."""
    game = fresh_game()
    spell_info = make_instant('Heist', cmc=6, oracle='Sneak\nDraw two cards.')
    assert has_sneak_card(spell_info)
    zones = game.zones
    player_hand = zones.player_zones[0].hand
    player_hand.append(CardObject(controller_idx=0, owner_idx=0, card_info=spell_info))
    player_hand.append(CardObject(controller_idx=0, owner_idx=0, card_info=make_land('Island')))
    sneak_input = SneakCastInput(spell_hand_idx=0, land_hand_indices=(1,))
    remaining, exiled_count, sneak_err = resolve_sneak_for_cast(
        spell_info,
        6,
        zones,
        0,
        sneak_input,
    )
    assert sneak_err is None
    assert remaining == 4
    assert exiled_count == 1
    assert len(zones.player_zones[0].exile) == 1
