"""Unit tests for batch 38 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.other.amplify import apply_amplify_etb, has_amplify_card
from engine.abilities.keywords.other.battle_cry import (
    apply_battle_cry_on_attack,
    has_battle_cry_card,
)
from engine.abilities.keywords.other.bushido import apply_bushido_when_engaged, has_bushido_card
from engine.abilities.keywords.other.dethrone import (
    apply_dethrone_on_combat_damage_to_player,
    has_dethrone_card,
)
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.graft import has_graft_card
from engine.abilities.keywords.other.renown import (
    apply_renown_on_combat_damage_to_player,
    has_renown_card,
    is_renowned,
)
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_dethrone_rewards_damage_to_highest_life_player():
    """Dethrone triggers when combat damage hits the player with the most life."""
    game = fresh_game()
    game.players[1].life = 25
    card = make_creature('Marchesa', 4, 4, oracle='Dethrone — Draw a card.')
    queen = place_on_battlefield(card, 0, game.zones)
    assert has_dethrone_card(card)
    throne_detail = apply_dethrone_on_combat_damage_to_player(game, queen, 3, 1)
    assert throne_detail is not None
    assert 'draw' in throne_detail.lower()


def test_battle_cry_keyword_boosts_fellow_attackers():
    """Battle cry detection and +1/+0 on other attacking creatures."""
    game = fresh_game()
    herald_card = make_creature('Herald', 2, 2, oracle='Battle cry')
    assert has_battle_cry_card(herald_card)
    herald = place_on_battlefield(herald_card, 0, game.zones, sick=False)
    recruit = place_on_battlefield(make_creature('Recruit', 1, 1), 0, game.zones, sick=False)
    attack_ids = [str(herald.obj_id), str(recruit.obj_id)]
    cry_detail = apply_battle_cry_on_attack(game, herald, attack_ids)
    assert cry_detail is not None
    assert 'battle cry' in cry_detail.lower()
    assert recruit.counters.get('battle_cry', 0) == 1


def test_bushido_grants_counters_once_in_combat():
    """Bushido keyword detection and single combat bonus."""
    card = make_creature('Ronin', 2, 2, oracle='Bushido 1')
    assert has_bushido_card(card)
    samurai = place_on_battlefield(card, 0, fresh_game().zones)
    bushido_detail = apply_bushido_when_engaged(samurai)
    assert bushido_detail is not None
    assert samurai.counters.get('+1/+1') == 1
    assert apply_bushido_when_engaged(samurai) is None


def test_renown_marks_creature_after_player_damage():
    """Renown adds +1/+1 and marks the creature renowned."""
    card = make_creature('Knight', 3, 3, oracle='Renown 1')
    assert has_renown_card(card)
    knight = place_on_battlefield(card, 0, fresh_game().zones)
    renown_detail = apply_renown_on_combat_damage_to_player(knight, 2)
    assert renown_detail is not None
    assert knight.counters.get('+1/+1') == 1
    assert is_renowned(knight)


def test_amplify_reports_when_hand_has_no_matches():
    """Amplify keyword detection with no matching creatures in hand."""
    game = fresh_game()
    card = make_creature('Captain', 3, 3, oracle='Amplify 2')
    assert has_amplify_card(card)
    captain = place_on_battlefield(card, 0, game.zones)
    amplify_detail = apply_amplify_etb(game, captain)
    assert amplify_detail is not None
    assert 'no matches' in amplify_detail
    assert captain.counters.get('+1/+1', 0) == 0


def test_graft_etb_hook_moves_counter_from_donor():
    """Graft is detected on the card and wired through ETB registration."""
    game = fresh_game()
    donor = place_on_battlefield(make_creature('Donor', 2, 2), 0, game.zones)
    donor.counters['+1/+1'] = 1
    card = make_creature('Receiver', 1, 1, oracle='Graft')
    assert has_graft_card(card)
    receiver = place_on_battlefield(card, 0, game.zones)
    etb_details = apply_etb_other_abilities(game, receiver)
    assert any('graft' in line for line in etb_details)
    assert receiver.counters.get('+1/+1', 0) == 1
