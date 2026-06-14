"""Unit tests for awaken and gravestorm (batch 21)."""

from __future__ import annotations

from engine.abilities.keywords.casting.awaken import (
    apply_awaken_on_resolve,
    awaken_mana_extra,
    has_awaken,
    normalize_paid_awaken,
)
from engine.abilities.keywords.casting.gravestorm import (
    gravestorm_copy_count,
    has_gravestorm,
)
from engine.core.game_object import CardObject, Target
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.game.helpers import SpellCastContext, spell_on_stack_from_context
from tests.conftest import fresh_game, make_instant, make_land

_AWAKEN_ORACLE = (
    'Awaken 3 — {2}{U}\n'
    'Draw a card.'
)
_GRAVESTORM_ORACLE = 'Gravestorm\nDeal 3 damage to any target.'


def test_awaken_adds_extra_mana():
    """Awaken cost is added when paid."""
    card = make_instant('Growth', cmc=3, oracle=_AWAKEN_ORACLE)
    assert has_awaken(card)
    assert normalize_paid_awaken(card, True)
    assert awaken_mana_extra(card, True) == 3


def test_awaken_animates_land_on_resolve():
    """Paying awaken puts a land onto the battlefield as a creature."""
    game = fresh_game()
    spell = make_instant('Growth', cmc=3, oracle=_AWAKEN_ORACLE)
    land = make_land('Island')
    game.zones.player_zones[0].hand.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=land),
    )
    detail = apply_awaken_on_resolve(game.zones, 0, spell, 0)
    assert detail is not None
    assert 'awaken Island' in detail
    assert len(game.zones.battlefield) == 1
    assert game.zones.battlefield[0].counters.get('+1/+1', 0) == 3


def test_gravestorm_copies_match_permanents_died():
    """Gravestorm copies equal permanents that died this turn."""
    card = make_instant('Bitter', cmc=5, oracle=_GRAVESTORM_ORACLE)
    assert has_gravestorm(card)
    assert gravestorm_copy_count(2) == 2


def test_gravestorm_puts_copies_on_stack():
    """Casting gravestorm with deaths on stack adds copies."""
    game = fresh_game()
    spell = make_instant('Bitter', cmc=5, oracle=_GRAVESTORM_ORACLE)
    game.meta.deaths.permanents_died = 2
    card = CardObject(controller_idx=0, owner_idx=0, card_info=spell)
    context = SpellCastContext()
    game.stack.push(spell_on_stack_from_context(0, card, [Target(player_idx=1)], context))
    logs = apply_post_cast_modifiers(game, 0, card, [Target(player_idx=1)], context)
    assert any('gravestorm' in line for line in logs)
    assert len(game.stack.objects) == 3
