"""Unit tests for ability_other batch 9: boast, casualty, encore."""

from __future__ import annotations

from engine.abilities.keywords.casting.casualty import (
    casualty_power_required,
    casualty_sacrifice_error,
    has_casualty,
)
from engine.abilities.keywords.other.boast import (
    apply_boast,
    can_boast,
    mark_attacked_this_turn,
)
from engine.abilities.keywords.other.encore import (
    apply_encore_from_graveyard,
    encore_mana_needed,
    has_encore_card,
)
from engine.core.game_object import CardObject, SpellCastPayment, Target, _AlternateModes
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.game.helpers import SpellCastContext, spell_on_stack_from_context
from tests.conftest import (
    add_to_library,
    fresh_game,
    make_creature,
    make_instant,
    place_on_battlefield,
)

_CASUALTY_ORACLE = (
    'Casualty 2 (As an additional cost to cast this spell, you may sacrifice '
    'a creature with power 2 or greater. When you do, copy this spell and you '
    'may choose new targets for the copy.)\n'
    'Shock deals 2 damage to any target.'
)
_BOAST_ORACLE = (
    '{1}{G}: Boast — Draw a card. '
    '(Activate only during your main phase while this creature is attacking.)'
)


def _draw_cards(game, player_idx: int, count: int) -> list:
    drawn = []
    library = game.zones.player_zones[player_idx].library
    for _ in range(count):
        if library:
            drawn.append(library.pop())
    return drawn


def test_casualty_requires_creature_power():
    """Casualty validates sacrifice power before copying."""
    game = fresh_game()
    spell = make_instant('Shock', cmc=1, mana_cost='{R}', oracle=_CASUALTY_ORACLE)
    weak = place_on_battlefield(make_creature('Weak', 1, 1), 0, game.zones)
    assert has_casualty(spell)
    assert casualty_power_required(spell) == 2
    err = casualty_sacrifice_error(game.zones, 0, spell, True, [weak.obj_id])
    assert err is not None


def test_casualty_copy_on_stack():
    """Paying casualty puts a copy on the stack."""
    game = fresh_game()
    spell = make_instant('Shock', cmc=0, mana_cost='', oracle=_CASUALTY_ORACLE)
    card = CardObject(controller_idx=0, owner_idx=0, card_info=spell)
    context = SpellCastContext(payment=SpellCastPayment(modes=_AlternateModes(casualty=True)))
    targets = [Target(player_idx=1)]
    game.stack.push(spell_on_stack_from_context(0, card, targets, context))
    logs = apply_post_cast_modifiers(game, 0, card, targets, context)
    assert any('casualty copy' in line for line in logs)
    assert len(game.stack.objects) == 2


def test_boast_draws_when_attacking():
    """Boast draws a card after the creature attacked."""
    game = fresh_game()
    boaster = place_on_battlefield(
        make_creature('Boaster', 2, 2, oracle=_BOAST_ORACLE),
        0,
        game.zones,
        sick=False,
    )
    mark_attacked_this_turn(boaster)
    assert can_boast(boaster, 'main2')
    add_to_library(make_creature('Top', 1, 1), 0, game.zones)
    library_before = len(game.zones.player_zones[0].library)
    detail = apply_boast(
        boaster,
        0,
        lambda player_idx, count: _draw_cards(game, player_idx, count),
    )
    assert detail
    assert len(game.zones.player_zones[0].library) == library_before - 1
    assert not can_boast(boaster, 'main2')


def test_encore_from_graveyard_creates_token():
    """Encore exiles a creature and creates an attacking token copy."""
    game = fresh_game()
    creature = make_creature('Siege', 3, 3, oracle='Encore {2}{B}')
    assert has_encore_card(creature)
    assert encore_mana_needed(creature) == 3
    game.zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=creature),
    )
    detail = apply_encore_from_graveyard(game, game.zones, 0, 0)
    assert detail
    assert len(game.zones.player_zones[0].graveyard) == 0
    assert len(game.zones.player_zones[0].exile) == 1
    tokens = [p for p in game.zones.battlefield if p.is_token]
    assert len(tokens) == 1
    assert tokens[0].name == 'Siege'
    assert tokens[0].tapped
