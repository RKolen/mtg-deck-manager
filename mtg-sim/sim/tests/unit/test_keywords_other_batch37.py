"""Unit tests for batch 37 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.other.devour import apply_devour_etb, has_devour_card
from engine.abilities.keywords.other.extort import apply_extort_on_spell_cast, has_extort_card
from engine.abilities.keywords.other.fabricate import apply_fabricate_etb, has_fabricate_card
from engine.abilities.keywords.other.flanking import apply_flanking_on_block, has_flanking_card
from engine.abilities.keywords.other.frenzy import apply_frenzy_on_unblocked_attack, has_frenzy_card
from engine.abilities.keywords.other.mentor import apply_mentor_on_attack, has_mentor_card
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_flanking_weakens_blocker_without_flanking():
    """Flanking gives a blocker -1/-1 when it lacks flanking."""
    game = fresh_game()
    attacker_card = make_creature('Cavalry', 2, 2, oracle='Flanking')
    blocker_card = make_creature('Foot Soldier', 2, 2)
    attacker = place_on_battlefield(attacker_card, 0, game.zones)
    blocker = place_on_battlefield(blocker_card, 1, game.zones)
    assert has_flanking_card(attacker_card)
    detail = apply_flanking_on_block(attacker, blocker)
    assert detail is not None
    assert blocker.counters.get('-1/-1') == 1


def test_frenzy_triggers_on_unblocked_attack():
    """Frenzy reports when a creature attacks unblocked."""
    game = fresh_game()
    card = make_creature('Berserker', 3, 3, oracle='Frenzy — Draw a card.')
    attacker = place_on_battlefield(card, 0, game.zones)
    assert has_frenzy_card(card)
    detail = apply_frenzy_on_unblocked_attack(game, attacker, blocked=False)
    assert detail is not None
    assert 'draw' in detail.lower()


def test_devour_sacrifices_creatures_for_counters():
    """Devour sacrifices other creatures and grants +1/+1 counters."""
    game = fresh_game()
    place_on_battlefield(make_creature('Snack', 1, 1), 0, game.zones)
    card = make_creature('Dragon', 4, 4, oracle='Devour 1')
    devourer = place_on_battlefield(card, 0, game.zones)
    assert has_devour_card(card)
    detail = apply_devour_etb(game, devourer)
    assert detail is not None
    assert devourer.counters.get('+1/+1') == 1


def test_fabricate_puts_counters_on_creature():
    """Fabricate adds +1/+1 counters when no artifact token is requested."""
    game = fresh_game()
    card = make_creature('Welder', 2, 2, oracle='Fabricate 2')
    welder = place_on_battlefield(card, 0, game.zones)
    assert has_fabricate_card(card)
    detail = apply_fabricate_etb(game.zones, welder)
    assert detail is not None
    assert welder.counters.get('+1/+1') == 2


def test_extort_drains_opponent_on_spell_cast():
    """Extort drains life from opponents when you cast a spell."""
    game = fresh_game()
    card = make_creature('Pontiff', 2, 3, oracle='Extort')
    place_on_battlefield(card, 0, game.zones)
    assert has_extort_card(card)
    detail = apply_extort_on_spell_cast(game, 0)
    assert detail is not None
    assert game.players[1].life == 19
    assert game.players[0].life == 21


def test_mentor_buffs_smaller_attacker():
    """Mentor keyword detection and +1/+1 on a weaker attacker."""
    game = fresh_game()
    warden_card = make_creature('Warden', 3, 3, oracle='Mentor')
    assert has_mentor_card(warden_card)
    warden = place_on_battlefield(warden_card, 0, game.zones, sick=False)
    pupil = place_on_battlefield(make_creature('Pupil', 1, 2), 0, game.zones, sick=False)
    attack_ids = [str(warden.obj_id), str(pupil.obj_id)]
    mentor_detail = apply_mentor_on_attack(game, warden, attack_ids)
    assert mentor_detail is not None
    assert 'mentor' in mentor_detail.lower()
    assert pupil.counters.get('+1/+1') == 1
