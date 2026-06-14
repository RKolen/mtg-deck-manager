"""Unit tests for offering, impending, and For Mirrodin! (batch 23)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaModifiers,
    _SacManaModifiers,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.casting.for_mirrodin import (
    for_mirrodin_sacrifice_error,
    has_for_mirrodin,
    normalize_paid_for_mirrodin,
)
from engine.abilities.keywords.casting.impending import (
    apply_impending_on_resolve,
    has_impending,
    impending_mana_extra,
    normalize_paid_impending,
)
from engine.abilities.keywords.casting.offering import (
    has_offering,
    normalize_offering_cast,
    offering_mana_reduction,
    offering_sacrifice_error,
)
from engine.core.game_object import CardObject
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_artifact,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)

_OFFERING_ORACLE = (
    'Offering (You may cast this card any time you could cast an instant '
    'by sacrificing a creature.)\n'
    'When this artifact enters, draw a card.'
)
_IMPENDING_ORACLE = (
    'Impending 4 — {2}{U}\n'
    'Draw two cards.'
)
_FOR_MIRRODIN_ORACLE = (
    'For Mirrodin! (When you cast this Equipment, you may sacrifice a creature. '
    'If you do, create a 1/1 colorless Soldier artifact creature token.)\n'
    'Equipped creature gets +2/+2.'
)


def _make_equipment(name: str, oracle: str):
    """Create equipment CardInfo for tests."""
    return make_card(
        name=name,
        type_line='Artifact — Equipment',
        oracle=oracle,
        mana_cost='{3}',
        stats=_CardStats(cmc=3.0, pt='0/0'),
    )


def test_offering_reduces_mana_when_cast_with_sacrifice():
    """Offering lowers the mana cost when used."""
    card = make_artifact('Altar', cmc=4, oracle=_OFFERING_ORACLE)
    assert has_offering(card)
    assert normalize_offering_cast(card, True)
    assert offering_mana_reduction(card, True) == 2
    mana, _life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            modifiers=CastManaModifiers(
                sac=_SacManaModifiers(cast_for_offering=True),
            ),
        ),
    )
    assert mana == 2


def test_impending_enters_as_creature():
    """Impending resolves the spell as an N/N creature."""
    game = fresh_game()
    spell = make_instant('Omen', cmc=3, oracle=_IMPENDING_ORACLE)
    assert has_impending(spell)
    assert normalize_paid_impending(spell, True)
    assert impending_mana_extra(spell, True) == 3
    card = CardObject(controller_idx=0, owner_idx=0, card_info=spell)
    detail = apply_impending_on_resolve(game.zones, 0, card)
    assert detail is not None
    assert 'impending' in detail
    assert len(game.zones.battlefield) == 1
    perm = game.zones.battlefield[0]
    assert perm.counters.get('+1/+1', 0) == 4


def test_for_mirrodin_on_equipment():
    """For Mirrodin! is recognized on equipment."""
    card = _make_equipment('Sword', _FOR_MIRRODIN_ORACLE)
    assert has_for_mirrodin(card)
    assert normalize_paid_for_mirrodin(card, True)


def test_offering_sacrifice_validation():
    """Offering requires sacrificing a creature you control."""
    game = fresh_game()
    card = make_artifact('Engine', cmc=3, oracle=_OFFERING_ORACLE)
    creature = place_on_battlefield(make_creature('Goblin', 1, 1), 0, game.zones)
    err = offering_sacrifice_error(
        game.zones,
        0,
        card,
        True,
        [creature.obj_id],
    )
    assert err is None


def test_for_mirrodin_sacrifice_validation():
    """For Mirrodin! requires sacrificing a creature you control."""
    game = fresh_game()
    card = _make_equipment('Blade', _FOR_MIRRODIN_ORACLE)
    creature = place_on_battlefield(make_creature('Soldier', 1, 1), 0, game.zones)
    err = for_mirrodin_sacrifice_error(
        game.zones,
        0,
        card,
        True,
        [creature.obj_id],
    )
    assert err is None
