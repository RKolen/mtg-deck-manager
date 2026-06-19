"""Unit tests for living metal, phasing, intensity, ravenous, and soulbond (batch 26)."""

from __future__ import annotations

from engine.abilities.keywords.combat import can_attack, can_block
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.intensity import (
    apply_intensity_on_spell_cast,
    has_intensity,
)
from engine.abilities.keywords.other.living_metal import (
    activate_living_metal_for_combat,
    deactivate_living_metal_after_combat,
    has_living_metal,
    is_living_metal_creature,
)
from engine.abilities.keywords.other.phasing import has_phasing, resolve_phasing_upkeep
from engine.abilities.keywords.other.ravenous import apply_ravenous_etb, has_ravenous
from engine.abilities.keywords.other.soulbond import apply_soulbond_etb, has_soulbond
from engine.core.game_object import CardObject
from tests.conftest import (
    fresh_game,
    make_artifact,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_living_metal_animates_artifact_for_combat():
    """Living metal artifacts can attack during combat."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_artifact('Golem', cmc=3, oracle='Living metal'),
        0,
        game.zones,
    )
    assert has_living_metal(perm)
    details = activate_living_metal_for_combat(game, 0)
    assert details
    assert is_living_metal_creature(perm)
    perm.sick = False
    assert can_attack(perm)
    deactivate_living_metal_after_combat(game, 0)
    assert not is_living_metal_creature(perm)


def test_phasing_toggles_on_upkeep():
    """Phasing permanents toggle phased status at upkeep."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Slider', 2, 2, oracle='Phasing'),
        0,
        game.zones,
    )
    assert has_phasing(perm)
    details = resolve_phasing_upkeep(game, 0)
    assert details
    assert perm.phased_out
    assert not can_block(perm)


def test_intensity_increments_on_spell_cast():
    """Intensity counters rise when you cast a spell."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Channeler', 2, 2, oracle='Intensity 2'),
        0,
        game.zones,
    )
    assert has_intensity(perm)
    spell = make_instant('Bolt', cmc=1)
    details = apply_intensity_on_spell_cast(game, 0, spell)
    assert details
    assert perm.counters.get('intensity', 0) == 1


def test_ravenous_puts_counters_from_hand_size():
    """Ravenous enters with +1/+1 counters equal to hand size."""
    game = fresh_game()
    for _ in range(3):
        game.zones.player_zones[0].hand.append(
            CardObject(controller_idx=0, owner_idx=0, card_info=make_creature('Card', 1, 1)),
        )
    perm = place_on_battlefield(
        make_creature('Devourer', 2, 2, oracle='Ravenous'),
        0,
        game.zones,
    )
    assert has_ravenous(perm)
    detail = apply_ravenous_etb(game, perm)
    assert detail is not None
    assert perm.counters.get('+1/+1', 0) == 3


def test_soulbond_pairs_with_another_creature():
    """Soulbond pairs with another unpaired creature on ETB."""
    game = fresh_game()
    partner = place_on_battlefield(
        make_creature('Partner', 2, 2, oracle='Soulbond'),
        0,
        game.zones,
    )
    incoming = place_on_battlefield(
        make_creature('Joiner', 2, 2, oracle='Soulbond'),
        0,
        game.zones,
    )
    assert has_soulbond(incoming)
    detail = apply_soulbond_etb(game, incoming)
    assert detail is not None
    assert 'soulbond' in detail
    assert incoming.counters.get('soulbond') == partner.obj_id


def test_ravenous_etb_hook_runs_from_registry():
    """Ravenous is wired through apply_etb_other_abilities."""
    game = fresh_game()
    game.zones.player_zones[0].hand.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_creature('Extra', 1, 1)),
    )
    perm = place_on_battlefield(
        make_creature('Hungry', 3, 3, oracle='Ravenous'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, perm)
    assert any('ravenous' in line for line in details)
