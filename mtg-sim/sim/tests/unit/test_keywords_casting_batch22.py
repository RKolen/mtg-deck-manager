"""Unit tests for gift and fuse (batch 22)."""

from __future__ import annotations

from engine.abilities.keywords.casting.fuse import has_fuse, normalize_paid_fuse
from engine.abilities.keywords.casting.gift import (
    gift_opponent_draws,
    has_gift,
    normalize_paid_gift,
)
from engine.core.game_object import CardObject, Target
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.game.cast_context import _HandCastExtras
from engine.game.helpers import SpellCastContext, spell_on_stack_from_context
from tests.conftest import fresh_game, make_instant

_GIFT_ORACLE = (
    'Gift an extra card (You may pay an additional cost as you cast this spell. '
    'If you do, an opponent draws a card.)\n'
    'Draw a card.'
)
_FUSE_ORACLE = (
    'Fuse (You may cast one or both halves of this card from your hand.)\n'
    'Deal 3 damage to any target.'
)


def test_gift_opponent_draws_when_paid():
    """Paying gift makes the opponent draw."""
    card = make_instant('Present', cmc=2, oracle=_GIFT_ORACLE)
    assert has_gift(card)
    assert normalize_paid_gift(card, True)
    assert gift_opponent_draws(card, True)


def test_fuse_puts_copy_on_stack():
    """Paying fuse puts a second copy on the stack."""
    game = fresh_game()
    spell = make_instant('Joined', cmc=4, oracle=_FUSE_ORACLE)
    assert has_fuse(spell)
    assert normalize_paid_fuse(spell, True)
    card = CardObject(controller_idx=0, owner_idx=0, card_info=spell)
    context = SpellCastContext(extras=_HandCastExtras(fuse=True))
    game.stack.push(spell_on_stack_from_context(0, card, [Target(player_idx=1)], context))
    logs = apply_post_cast_modifiers(game, 0, card, [Target(player_idx=1)], context)
    assert any('fuse copy' in line for line in logs)
    assert len(game.stack.objects) == 2
