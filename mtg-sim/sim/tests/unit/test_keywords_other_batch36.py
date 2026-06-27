"""Unit tests for batch 36 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.other.afflict import apply_afflict_on_attack, has_afflict_card
from engine.abilities.keywords.other.annihilator import (
    apply_annihilator_on_attack,
    has_annihilator_card,
)
from engine.abilities.keywords.other.cipher import CipherEffect, has_cipher_card
from engine.abilities.keywords.other.enlist import apply_enlist_on_attack, has_enlist_card
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.exalted import apply_exalted_on_attack, has_exalted_card
from engine.abilities.keywords.other.mobilize import apply_mobilize_on_attack, has_mobilize_card
from engine.core.game_object import CardObject, TriggeredAbilityOnStack
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_afflict_drains_defender_on_attack():
    """Afflict makes the defending player lose life when attacking."""
    game = fresh_game()
    card = make_creature('Tormentor', 2, 2, oracle='Afflict')
    attacker = place_on_battlefield(card, 0, game.zones)
    assert has_afflict_card(card)
    detail = apply_afflict_on_attack(game, attacker)
    assert detail is not None
    assert game.players[1].life == 19


def test_annihilator_destroys_opponent_permanents():
    """Annihilator destroys permanents the defending player controls."""
    game = fresh_game()
    place_on_battlefield(make_creature('Defender', 2, 2), 1, game.zones)
    card = make_creature('Ulamog', 8, 8, oracle='Annihilator 1')
    attacker = place_on_battlefield(card, 0, game.zones)
    assert has_annihilator_card(card)
    detail = apply_annihilator_on_attack(game, attacker)
    assert detail is not None
    assert len(game.zones.permanents_of(1)) == 0


def test_exalted_buffs_solo_attacker():
    """Exalted grants +1/+1 when this creature attacks alone."""
    game = fresh_game()
    card = make_creature('Rafiq', 3, 3, oracle='Exalted')
    attacker = place_on_battlefield(card, 0, game.zones)
    assert has_exalted_card(card)
    detail = apply_exalted_on_attack(game, attacker, solo_attack=True)
    assert detail is not None
    assert attacker.counters.get('+1/+1') == 1


def test_mobilize_creates_soldier_tokens():
    """Mobilize creates Soldier tokens when this creature attacks."""
    game = fresh_game()
    card = make_creature('Commander', 3, 3, oracle='Mobilize 2')
    leader = place_on_battlefield(card, 0, game.zones)
    assert has_mobilize_card(card)
    detail = apply_mobilize_on_attack(game, leader)
    assert detail is not None
    soldiers = [p for p in game.zones.battlefield if 'Soldier' in p.type_line]
    assert len(soldiers) == 2


def test_enlist_taps_non_attacking_creature():
    """Enlist taps an untapped creature that is not attacking."""
    game = fresh_game()
    helper = place_on_battlefield(make_creature('Recruit', 1, 1), 0, game.zones)
    card = make_creature('Veteran', 2, 2, oracle='Enlist')
    attacker = place_on_battlefield(card, 0, game.zones, sick=False)
    assert has_enlist_card(card)
    detail = apply_enlist_on_attack(
        game,
        attacker,
        [str(attacker.obj_id)],
    )
    assert detail is not None
    assert helper.tapped


def test_cipher_triggers_on_instant_cast():
    """Cipher registers on ETB and triggers when you cast an instant."""
    game = fresh_game()
    card = make_creature('Encoded', 1, 1, oracle='Cipher — Draw a card.')
    host = place_on_battlefield(card, 0, game.zones)
    assert has_cipher_card(card)
    apply_etb_other_abilities(game, host)
    game.fire_spell_cast_triggers(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_instant('Opt', oracle='Draw a card.'),
        ),
    )
    trigger = game.stack.top
    assert isinstance(trigger, TriggeredAbilityOnStack)
    assert isinstance(trigger.effect, CipherEffect)
