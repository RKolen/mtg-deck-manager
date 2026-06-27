"""Unit tests for batch 40 other keywords."""

from __future__ import annotations

from engine.abilities.keywords.other.augment import has_augment_card
from engine.abilities.keywords.other.craft import apply_craft, has_craft_card
from engine.abilities.keywords.other.dredge import apply_dredge, has_dredge_card
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.exhaust import (
    can_use_exhaust_ability,
    has_exhaust_card,
    mark_exhaust_used,
)
from engine.abilities.keywords.other.offspring import has_offspring_card
from engine.abilities.keywords.other.prowl import has_prowl_card, mark_prowl_cast, prowl_unblockable
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_artifact, make_creature, place_on_battlefield


def test_offspring_keyword_spawns_token_via_etb_hook():
    """Offspring card detection and token creation through ETB registration."""
    game = fresh_game()
    card = make_creature('Brood', 3, 3, oracle='Offspring {3}')
    assert has_offspring_card(card)
    brood = place_on_battlefield(card, 0, game.zones)
    etb_lines = apply_etb_other_abilities(game, brood)
    assert any('offspring' in line for line in etb_lines)
    assert any(p.is_token for p in game.zones.battlefield)


def test_craft_keyword_exiles_artifact_payment():
    """Craft card detection and artifact exile when crafting."""
    game = fresh_game()
    craft_oracle = (
        '{2}, Exile an artifact you control: Craft this artifact '
        'into a creature.'
    )
    card = make_artifact('Clay Statue', oracle=craft_oracle)
    assert has_craft_card(card)
    statue = place_on_battlefield(card, 0, game.zones)
    payment = place_on_battlefield(make_artifact('Shard'), 0, game.zones)
    craft_detail = apply_craft(game, statue, [payment.obj_id])
    assert craft_detail is not None
    assert statue.counters.get('crafted') == 1


def test_dredge_keyword_mills_from_library():
    """Dredge card detection and library milling."""
    game = fresh_game()
    zones = game.zones
    zones.player_zones[0].library.append(
        CardObject(
            controller_idx=0,
            owner_idx=0,
            card_info=make_creature('Top Card', 1, 1),
        ),
    )
    dredge_card = make_creature('Golgari', 6, 6, oracle='Dredge 2')
    assert has_dredge_card(dredge_card)
    zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=dredge_card),
    )
    dredge_err, dredge_detail, milled = apply_dredge(zones, 0, 0)
    assert dredge_err is None
    assert dredge_detail is not None
    assert len(milled) == 2


def test_augment_keyword_merges_onto_host():
    """Augment card detection and host merge on ETB."""
    game = fresh_game()
    place_on_battlefield(make_creature('Carrier', 2, 2), 0, game.zones)
    card = make_creature('Graftling', 2, 1, oracle='Augment {1}{G}')
    assert has_augment_card(card)
    graftling = place_on_battlefield(card, 0, game.zones)
    augment_lines = apply_etb_other_abilities(game, graftling)
    assert any('augment' in line for line in augment_lines)


def test_prowl_keyword_makes_attacker_unblockable_when_marked():
    """Prowl card detection and unblockable marker after cast."""
    card = make_creature('Skulk', 2, 2, oracle='Prowl {B}')
    assert has_prowl_card(card)
    game = fresh_game()
    skulk = place_on_battlefield(card, 0, game.zones, sick=False)
    mark_prowl_cast(skulk)
    assert prowl_unblockable(skulk, game)


def test_exhaust_keyword_allows_single_activation():
    """Exhaust card detection and once-per-game ability use."""
    card = make_creature('Titan', 4, 4, oracle='Exhaust — Draw two cards.')
    assert has_exhaust_card(card)
    titan = place_on_battlefield(card, 0, fresh_game().zones)
    assert can_use_exhaust_ability(titan)
    exhaust_detail = mark_exhaust_used(titan)
    assert exhaust_detail is not None
    assert not can_use_exhaust_ability(titan)
