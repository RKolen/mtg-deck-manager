"""Unit tests for ability_other batch 5: evoke, prowl, cipher."""

from __future__ import annotations

from engine.abilities.keywords.combat import legal_blocker
from engine.abilities.keywords.other.cipher import CipherEffect
from engine.abilities.keywords.other.cipher import is_cipher_instant_or_sorcery_cast
from engine.abilities.keywords.other.evoke import apply_evoke_on_etb, mark_evoked_cast
from engine.abilities.keywords.other.prowl import mark_prowl_cast, prowl_unblockable
from engine.abilities.keywords.other.register import register_permanent_other_keywords
from engine.core.game_object import CardObject
from engine.rules.triggers import SpellCastTriggerEvent, TriggerDefinition, TriggerKey
from tests.conftest import (_CardStats, fresh_game, make_card,make_creature,
                                make_instant, place_on_battlefield
                            )


def test_evoke_sacrifices_when_marked():
    """Evoke sacrifices the creature on ETB when cast for evoke."""
    game = fresh_game()
    creature = place_on_battlefield(
        make_creature('Mulldrifter', 2, 2, oracle='Flying\nEvoke {2}{U}'),
        0,
        game.zones,
    )
    mark_evoked_cast(creature)
    detail = apply_evoke_on_etb(game, creature)
    assert detail is not None
    assert 'evoked' in detail
    assert game.zones.find_permanent(creature.obj_id) is None


def test_prowl_unblockable_with_matching_graveyard():
    """Prowl makes the attacker unblockable when a matching creature is in the graveyard."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_card('Ninja', type_line='Creature — Human Ninja', oracle='Prowl {1}{B}',
                  stats=_CardStats(pt='2/2')
                ),
        0,
        game.zones,
        sick=False,
    )
    gy_card = make_card('Ally', type_line='Creature — Human Warrior', stats=_CardStats(pt='1/1'))
    game.zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=gy_card),
    )
    assert prowl_unblockable(attacker, game)
    blocker = place_on_battlefield(make_creature('Wall', 0, 4), 1, game.zones)
    assert not legal_blocker(blocker, attacker, game)


def test_prowl_counter_unblockable():
    """Prowl cast marker alone makes the attacker unblockable."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Ninja', 2, 2, oracle='Prowl {1}{B}'),
        0,
        game.zones,
        sick=False,
    )
    mark_prowl_cast(attacker)
    assert prowl_unblockable(attacker, game)


def test_cipher_registers_on_instant_cast():
    """Cipher triggers when the controller casts an instant."""
    game = fresh_game()
    source = place_on_battlefield(
        make_creature('Host', 1, 1, oracle='Cipher — Draw a card.'),
        0,
        game.zones,
    )
    register_permanent_other_keywords(source, game.trigger_registry)
    game.fire_spell_cast_triggers(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_instant('Bolt', oracle='Deal 3 damage.'),
        ),
        (),
    )
    trigger = game.stack.top
    assert trigger is not None
    effect = CipherEffect('Draw a card.')
    assert 'cipher' in effect.resolve(game, trigger)


def test_cipher_condition_matches_instant():
    """Cipher condition matches instant spells."""
    game = fresh_game()
    source = place_on_battlefield(make_creature('Host', 1, 1), 0, game.zones)
    definition = TriggerDefinition(
        source_permanent_id=source.obj_id,
        controller_idx=0,
        trigger_key=TriggerKey.SPELL_CAST,
        condition=is_cipher_instant_or_sorcery_cast,
    )
    event = SpellCastTriggerEvent(
        spell_id=1,
        controller_idx=0,
        spell_name='Bolt',
        type_line='Instant',
    )
    assert is_cipher_instant_or_sorcery_cast(event, game, definition)
