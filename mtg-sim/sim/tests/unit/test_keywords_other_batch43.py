"""Unit tests for batch 43 other keywords and shared helpers."""

from __future__ import annotations

from engine.abilities.keywords.other.affinity import (
    affinity_reduction,
    artifact_count,
    has_affinity_card,
)
from engine.abilities.keywords.other.augment import apply_augment_etb, has_augment
from engine.abilities.keywords.other.embalm_token import create_embalm_token_in_exile
from engine.abilities.keywords.other.face_down_turn import can_turn_up_face_down_keyword
from engine.abilities.keywords.other.host_creature import (
    find_host_creature,
    other_controlled_creatures,
)
from engine.abilities.keywords.other.megamorph import (
    apply_megamorph_turn_up,
    has_megamorph_card,
    megamorph_turn_up_mana_needed,
)
from engine.abilities.keywords.other.morph import has_morph
from engine.abilities.keywords.other.multikicker import has_multikicker_card
from engine.core.game_object import TokenObject
from tests.conftest import (
    fresh_game,
    make_artifact,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_affinity_card_discounts_per_controlled_artifact():
    """Affinity card detection and mana discount from artifacts."""
    game = fresh_game()
    card = make_creature('Frog', 1, 1, oracle='Affinity for artifacts\nFlying')
    assert has_affinity_card(card)
    place_on_battlefield(make_artifact('Relic'), 0, game.zones)
    place_on_battlefield(make_artifact('Core'), 0, game.zones)
    assert artifact_count(game.zones, 0) == 2
    assert affinity_reduction(card, game.zones, 0) == 2


def test_embalm_token_copies_creature_stats_in_exile():
    """Embalm token helper exiles a zombie with the source creature's stats."""
    game = fresh_game()
    honored = make_creature('Honored', 3, 2, oracle='Embalm {3}{W}')
    detail = create_embalm_token_in_exile(game.zones, 0, honored)
    assert 'embalmed' in detail
    token = game.zones.player_zones[0].exile[-1]
    assert isinstance(token, TokenObject)
    assert token.power == '3'
    assert token.toughness == '2'
    assert 'Zombie' in token.type_line


def test_face_down_turn_allows_main_phase_turn_up():
    """Face-down turn helper gates morph turn-up to main phases."""
    game = fresh_game()
    card = make_creature('Shifter', 2, 2, oracle='Morph {1}{G}')
    perm = place_on_battlefield(card, 0, game.zones)
    perm.face_down = True
    assert can_turn_up_face_down_keyword(perm, game, 0, 'main1', has_morph)
    assert not can_turn_up_face_down_keyword(perm, game, 0, 'attack', has_morph)


def test_host_creature_finds_augment_target():
    """Host creature helper selects another creature for augment."""
    game = fresh_game()
    host = place_on_battlefield(make_creature('Host', 2, 2), 0, game.zones)
    augment_card = make_creature('Graft', 1, 1, oracle='Augment {2}{G}')
    augment_perm = place_on_battlefield(augment_card, 0, game.zones)
    others = other_controlled_creatures(augment_perm, game.zones.battlefield)
    assert host in others
    chosen = find_host_creature(
        augment_perm,
        game.zones.battlefield,
        exclude=has_augment,
    )
    assert chosen is not None
    assert chosen.obj_id == host.obj_id
    assert apply_augment_etb(game.zones, augment_perm, game.zones.battlefield) is not None


def test_megamorph_card_adds_counter_on_turn_up():
    """Megamorph card detection and +1/+1 counter when turned face up."""
    game = fresh_game()
    card = make_creature('Sagu', 4, 4, oracle='Megamorph {2}{G}')
    assert has_megamorph_card(card)
    assert megamorph_turn_up_mana_needed(card) == 3
    perm = place_on_battlefield(card, 0, game.zones)
    perm.face_down = True
    detail = apply_megamorph_turn_up(game, perm)
    assert detail is not None
    assert perm.counters.get('+1/+1') == 1


def test_multikicker_card_detects_repeatable_kicker():
    """Multikicker card detection on spells with repeatable kicker."""
    card = make_instant('Strength', oracle='Multikicker {1}\nDraw a card.')
    assert has_multikicker_card(card)
    assert not has_multikicker_card(
        make_instant('Bolt', oracle='Kicker {1}\nDeal 3 damage.'),
    )
