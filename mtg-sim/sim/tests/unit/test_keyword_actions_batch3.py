"""Unit tests for keyword actions batch 3.

Treasure, Food, Monstrosity, Exert, Clash, and Harness.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.resolve import (
    ActionContext,
    resolve_spell_keyword_actions,
)
from engine.abilities.keywords.actions.specialty import (
    clash,
    exert_creature,
    has_clash,
    has_exert,
    has_harness,
    has_monstrosity,
    harness_energy,
    monstrosity_creature,
)
from engine.abilities.keywords.actions.tokens import (
    create_token_from_blueprint,
    has_food,
    has_treasure,
    treasure_token_blueprint,
)
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_treasure_creates_artifact_token():
    """Treasure creates a Treasure artifact token."""
    game = fresh_game()
    assert has_treasure('Create a Treasure token.')
    token_name = create_token_from_blueprint(
        game.zones,
        0,
        treasure_token_blueprint(),
    )
    assert 'Treasure' in token_name
    treasures = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == 0 and 'Treasure' in perm.type_line
    ]
    assert len(treasures) == 1


def test_food_spell_action_creates_food_tokens():
    """Food keyword action creates Food artifact tokens."""
    game = fresh_game()
    assert has_food('Create two Food tokens.')
    detail = resolve_spell_keyword_actions(ActionContext(
        zones=game.zones,
        game=game,
        controller_idx=0,
        oracle_text='Create two Food tokens.',
    ))
    assert detail is not None
    assert 'food' in detail.lower()
    foods = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == 0 and 'Food' in perm.type_line
    ]
    assert len(foods) == 2


def test_monstrosity_makes_creature_monstrous_with_counters():
    """Monstrosity adds +1/+1 counters and marks the creature monstrous."""
    game = fresh_game()
    hydra = place_on_battlefield(make_creature('Polukranos', 0, 0), 0, game.zones)
    oracle = 'Monstrosity 3.'
    assert has_monstrosity(oracle)
    detail = monstrosity_creature(game.zones, str(hydra.obj_id), oracle)
    assert detail is not None
    assert hydra.counters.get('+1/+1') == 3
    assert hydra.counters.get('monstrous') == 1


def test_exert_taps_creature_and_marks_exerted():
    """Exert taps a creature and marks it exerted."""
    game = fresh_game()
    warrior = place_on_battlefield(make_creature('Warrior', 4, 4), 0, game.zones)
    assert has_exert('Exert.')
    detail = exert_creature(game.zones, str(warrior.obj_id))
    assert detail is not None
    assert warrior.tapped
    assert warrior.counters.get('exerted') == 1


def test_clash_rewards_highest_mana_value_top_card():
    """Clash reveals library tops and draws for the higher mana value."""
    game = fresh_game()
    cheap = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_instant('Cheap', cmc=1.0),
    )
    pricey = CardObject(
        controller_idx=1,
        owner_idx=1,
        card_info=make_instant('Pricey', cmc=5.0),
    )
    game.zones.player_zones[0].library.append(cheap)
    game.zones.player_zones[1].library.append(pricey)
    assert has_clash('Clash with an opponent.')
    detail = clash(game.zones)
    assert 'clash' in detail
    assert 'Pricey' in detail
    assert len(game.zones.player_zones[1].hand) == 1


def test_harness_adds_energy_counter_to_creature():
    """Harness puts an energy counter on the target permanent."""
    game = fresh_game()
    reactor = place_on_battlefield(
        make_creature('Reactor', 2, 2, oracle='Harness energy from this creature.'),
        0,
        game.zones,
    )
    assert has_harness('Harness.')
    detail = harness_energy(game.zones, str(reactor.obj_id))
    assert detail is not None
    assert reactor.counters.get('energy') == 1
