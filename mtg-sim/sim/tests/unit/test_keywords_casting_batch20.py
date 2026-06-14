"""Unit tests for devoid and demonstrate (batch 20)."""

from __future__ import annotations

from engine.abilities.keywords.casting.conspire import conspire_color_match, spell_color_set
from engine.abilities.keywords.casting.devoid import has_devoid, spell_is_colorless_for_effects
from engine.abilities.keywords.casting.demonstrate import (
    has_demonstrate,
    normalize_paid_demonstrate,
)
from engine.core.game_object import CardObject, SpellCastPayment, Target, _KeywordPays
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.game.helpers import SpellCastContext, spell_on_stack_from_context
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield

_DEVOID_ORACLE = (
    'Devoid (This card has no color.)\n'
    'Counter target spell.'
)
_DEMONSTRATE_ORACLE = (
    'Demonstrate (When you cast this spell, you may copy it. '
    'If you do, choose new targets for the copy.)\n'
    'Draw a card.'
)


def test_devoid_makes_spell_colorless():
    """Devoid spells have no colors for conspire matching."""
    card = make_instant('Void', cmc=3, mana_cost='{1}{U}{U}', oracle=_DEVOID_ORACLE)
    assert has_devoid(card)
    assert spell_is_colorless_for_effects(card)
    assert spell_color_set(card) == set()


def test_devoid_blocks_conspire_without_colorless_creature():
    """Devoid spells cannot conspire without a colorless creature."""
    game = fresh_game()
    spell = make_instant('Void', cmc=3, mana_cost='{1}{U}{U}', oracle=_DEVOID_ORACLE)
    place_on_battlefield(make_creature('Elf', 1, 1, mana_cost='{G}'), 0, game.zones)
    assert not conspire_color_match(spell, game.zones, 0)


def test_demonstrate_copy_on_stack():
    """Paying demonstrate puts a copy on the stack."""
    game = fresh_game()
    spell = make_instant('Lesson', cmc=2, oracle=_DEMONSTRATE_ORACLE)
    assert has_demonstrate(spell)
    assert normalize_paid_demonstrate(spell, True)
    card = CardObject(controller_idx=0, owner_idx=0, card_info=spell)
    context = SpellCastContext(
        payment=SpellCastPayment(keywords=_KeywordPays(demonstrate=True)),
    )
    targets = [Target(player_idx=1)]
    game.stack.push(spell_on_stack_from_context(0, card, targets, context))
    logs = apply_post_cast_modifiers(game, 0, card, targets, context)
    assert any('demonstrate copy' in line for line in logs)
    assert len(game.stack.objects) == 2
