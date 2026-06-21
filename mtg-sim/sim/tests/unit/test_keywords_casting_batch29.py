"""Unit tests for warp, specialize, and compleated (batch 29)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaTiming,
    _TimingAvailability,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.casting.compleated import (
    compleated_life_extra,
    has_compleated,
    normalize_paid_compleated,
)
from engine.abilities.keywords.casting.specialize import (
    discard_for_specialize,
    has_specialize,
    normalize_specialize_cast,
    specialize_mana_needed,
)
from engine.abilities.keywords.casting.warp import (
    apply_warp_on_resolve,
    has_warp,
    normalize_warp_cast,
    warp_mana_needed,
)
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_warp_alternate_cost_and_exile_marker():
    """Warp uses lower cost and marks the permanent for end-step exile."""
    card = make_creature(
        'Skipper',
        4,
        4,
        oracle='Warp {1}{U}\nFlying',
        mana_cost='{3}{U}{U}',
    )
    assert has_warp(card)
    assert normalize_warp_cast(card, True)
    mana, _life = warp_mana_needed(card)
    assert mana == 2
    paid_mana, _paid_life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(timing=CastManaTiming(cast_for_warp=True)),
    )
    assert paid_mana == 2
    game = fresh_game()
    perm = place_on_battlefield(card, 0, game.zones)
    detail = apply_warp_on_resolve(perm)
    assert detail is not None
    assert perm.counters.get('warp_exile') == 1


def test_specialize_discards_from_hand():
    """Specialize pays an alternate cost and discards a card."""
    card = make_creature(
        'Student',
        2,
        2,
        oracle='Specialize {U}\nWhen this enters, draw a card.',
        mana_cost='{2}{U}',
    )
    assert has_specialize(card)
    assert normalize_specialize_cast(card, True)
    mana, _life = specialize_mana_needed(card)
    assert mana == 1
    game = fresh_game()
    discard = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_creature('Discard', 1, 1),
    )
    game.zones.player_zones[0].hand.append(discard)
    name = discard_for_specialize(game.zones, 0, 0)
    assert name == 'Discard'
    assert len(game.zones.player_zones[0].hand) == 0


def test_compleated_adds_life_cost():
    """Compleated adds 2 life per colored mana symbol."""
    card = make_instant(
        'Germ',
        cmc=2,
        oracle='Compleated\nDestroy target creature.',
        mana_cost='{1}{B}',
    )
    assert has_compleated(card)
    assert normalize_paid_compleated(card, True)
    assert compleated_life_extra(card, True) == 2
    _mana, life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            timing=CastManaTiming(
                available=_TimingAvailability(paid_compleated=True),
            ),
        ),
    )
    assert life == 2
