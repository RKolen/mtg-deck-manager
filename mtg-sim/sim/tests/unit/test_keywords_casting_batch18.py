"""Unit tests for cleave, conspire, and assist (batch 18)."""

from __future__ import annotations

from engine.abilities.keywords.casting.assist import has_assist, resolve_assist_for_cast
from engine.abilities.keywords.casting.cast_adjustments import (
    CastAdjustmentInput,
    resolve_cast_adjustments,
)
from engine.game.cast_context import CastManaReductionIds
from engine.abilities.keywords.casting.cleave import (
    cleave_mana_needed,
    has_cleave,
    normalize_cleave_cast,
)
from engine.abilities.keywords.casting.conspire import (
    conspire_color_match,
    conspire_error,
    conspire_extra_mana,
    has_conspire,
    normalize_paid_conspire,
)
from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaTiming,
    resolve_announce_cast_mana,
)
from engine.core.game_object import CardObject, SpellCastPayment, Target, _KeywordPays
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.game.helpers import SpellCastContext, spell_on_stack_from_context
from engine.game import create_game
from tests.conftest import (
    cast_announce_options,
    fresh_game,
    make_creature,
    make_deck,
    make_instant,
    place_on_battlefield,
    put_lands_on_battlefield,
)

_CLEAVE_ORACLE = (
    'Cleave {1}{R} (You may cast this spell for its cleave cost. '
    'If you do, copy it and choose different targets for the copy.)\n'
    'Deal 3 damage to any target.'
)
_CONSPIRE_ORACLE = (
    'Conspire (As you cast this spell, if you control a creature that shares '
    'a color with it, you may pay {2} to have a copy of it put onto the stack '
    'with the same targets.)\n'
    'Draw a card.'
)


def test_has_cleave_and_parses_alt_cost():
    """Cleave is detected and exposes an alternate mana cost."""
    card = make_instant('Bolt', cmc=3, mana_cost='{2}{R}', oracle=_CLEAVE_ORACLE)
    assert has_cleave(card)
    assert normalize_cleave_cast(card, True)
    assert cleave_mana_needed(card)[0] == 2


def test_cleave_copy_on_stack():
    """Paying cleave puts a copy on the stack."""
    game = fresh_game()
    spell = make_instant('Bolt', cmc=0, mana_cost='', oracle=_CLEAVE_ORACLE)
    card = CardObject(controller_idx=0, owner_idx=0, card_info=spell)
    context = SpellCastContext(payment=SpellCastPayment(keywords=_KeywordPays(cleave=True)))
    targets = [Target(player_idx=1)]
    game.stack.push(spell_on_stack_from_context(0, card, targets, context))
    logs = apply_post_cast_modifiers(game, 0, card, targets, context)
    assert any('cleave copy' in line for line in logs)
    assert len(game.stack.objects) == 2


def test_conspire_requires_matching_creature():
    """Conspire needs a creature that shares a color with the spell."""
    game = fresh_game()
    spell = make_instant('Draw', cmc=2, mana_cost='{U}{U}', oracle=_CONSPIRE_ORACLE)
    assert has_conspire(spell)
    assert not conspire_color_match(spell, game.zones, 0)
    place_on_battlefield(
        make_creature('Familiar', 1, 1, mana_cost='{U}'),
        0,
        game.zones,
    )
    assert conspire_color_match(spell, game.zones, 0)
    assert conspire_error(spell, True, game.zones, 0) is None
    assert normalize_paid_conspire(spell, True)
    assert conspire_extra_mana(spell, True) == 2


def test_assist_reduces_mana_in_cast_adjustments():
    """Assist lowers the caster's remaining mana obligation."""
    game = fresh_game()
    card = make_instant('Rally', cmc=4, oracle='Assist\nDraw two cards.')
    assert has_assist(card)
    mana, applied, err = resolve_assist_for_cast(card, 4, 2)
    assert err is None
    assert mana == 2
    assert applied == 2
    put_lands_on_battlefield(game, 4)
    result = resolve_cast_adjustments(
        card,
        4,
        CastAdjustmentInput(reductions=CastManaReductionIds(assist_mana=2)),
        game.zones,
        0,
    )
    assert result.error is None
    assert result.mana_needed == 2
    assert result.assist_mana_applied == 2


def test_announce_cast_mana_includes_conspire_payment():
    """Conspire adds its payment on top of the spell's mana cost."""
    card = make_instant('Draw', cmc=2, mana_cost='{U}{U}', oracle=_CONSPIRE_ORACLE)
    mana, _life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(timing=CastManaTiming(paid_conspire=True)),
    )
    assert mana == 4


def test_game_cleave_cast_puts_copy_on_stack():
    """Cleave cast from hand places the spell and a cleave copy on the stack."""
    bolt = make_instant(
        'Bolt',
        cmc=2,
        mana_cost='{1}{R}',
        oracle=_CLEAVE_ORACLE,
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    put_lands_on_battlefield(game, 3)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=bolt),
    ]
    data = game.action_cast_to_stack(
        0,
        cast_options=cast_announce_options(cast_for_cleave=True),
    )
    assert 'error' not in data
    assert len(game.state.stack.objects) >= 2
