"""Unit tests for splice, prototype, split second, and mayhem (batch 27)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaTiming,
    _FaceCastTiming,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.casting.mayhem import (
    can_cast_via_mayhem,
    has_mayhem,
    mayhem_mana_needed,
)
from engine.abilities.keywords.casting.prototype import (
    apply_prototype_on_etb,
    has_prototype,
    normalize_prototype_cast,
    prototype_mana_needed,
)
from engine.abilities.keywords.casting.splice import (
    has_splice,
    normalize_paid_splice,
    splice_mana_extra,
)
from engine.abilities.keywords.casting.split_second import (
    can_counter_stack_object,
    has_split_second,
)
from engine.core.game_object import CardObject, effective_power
from engine.game.helpers import SpellCastContext, spell_on_stack_from_context
from tests.conftest import (
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)


_PROTOTYPE_ORACLE = (
    'Prototype {2}{U} — You may cast this spell for its prototype cost. '
    'If you do, it enters the battlefield as a 3/3 artifact creature.'
)

_SPLICE_ORACLE = (
    'Splice onto Arcane {1}{R} (As you cast an Arcane spell, '
    'you may reveal this card from your hand and pay its splice cost. '
    'If you do, add this card\'s effects to that spell.)\n'
    'Deal 1 damage to any target.'
)

_MAYHEM_ORACLE = (
    'Mayhem {1}{R} (You may cast this card from your graveyard '
    'for its mayhem cost if you\'ve played a land this turn.)\n'
    'Deal 2 damage to any target.'
)


def test_prototype_alternate_cost_and_etb_stats():
    """Prototype uses lower cost and enters as smaller creature."""
    card = make_creature(
        'Walker',
        6,
        6,
        oracle=_PROTOTYPE_ORACLE,
        mana_cost='{4}{U}{U}',
    )
    assert has_prototype(card)
    assert normalize_prototype_cast(card, True)
    mana, _life = prototype_mana_needed(card)
    assert mana == 3
    paid_mana, _paid_life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            timing=CastManaTiming(face=_FaceCastTiming(prototype=True)),
        ),
    )
    assert paid_mana == 3
    game = fresh_game()
    perm = place_on_battlefield(card, 0, game.zones)
    detail = apply_prototype_on_etb(perm)
    assert detail is not None
    assert effective_power(perm) == 3


def test_splice_adds_extra_mana():
    """Splice pays an additional cost on top of the spell."""
    card = make_card(
        name='Arc',
        type_line='Instant — Arcane',
        oracle=_SPLICE_ORACLE,
        mana_cost='{1}{R}',
    )
    assert has_splice(card)
    assert normalize_paid_splice(card, True)
    assert splice_mana_extra(card, True) == 2


def test_split_second_blocks_counter():
    """Split second spells cannot be countered."""
    game = fresh_game()
    card_info = make_instant('Quicken', cmc=1, oracle='Split second\nDraw a card.')
    assert has_split_second(card_info)
    card = CardObject(controller_idx=0, owner_idx=0, card_info=card_info)
    spell = spell_on_stack_from_context(0, card, [], SpellCastContext())
    game.stack.push(spell)
    assert not can_counter_stack_object(spell)
    assert game.stack.counter_top(game.zones) is None
    assert game.stack.top is spell


def test_mayhem_requires_land_played():
    """Mayhem is only available from graveyard after a land drop."""
    game = fresh_game()
    card = make_instant('Rager', cmc=3, oracle=_MAYHEM_ORACLE)
    assert has_mayhem(card)
    assert not can_cast_via_mayhem(card, 'main1', True, land_played=False)
    game.players[0].land_played = True
    assert can_cast_via_mayhem(card, 'main1', True, land_played=True)
    mana, _life = mayhem_mana_needed(card)
    assert mana == 2
