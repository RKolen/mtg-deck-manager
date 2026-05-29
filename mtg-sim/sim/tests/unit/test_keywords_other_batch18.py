"""Unit tests for augment (batch 18)."""

from __future__ import annotations

from engine.abilities.keywords.other.augment import apply_augment_etb, has_augment
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_augment_merges_onto_host_creature():
    """Augment puts counters on a host and exiles the augment card."""
    game = fresh_game()
    host = place_on_battlefield(make_creature('Host', 2, 2), 0, game.zones)
    augment = place_on_battlefield(
        make_creature('Augmenter', 3, 2, oracle='Augment {2}{G} (Put this on a host.)'),
        0,
        game.zones,
    )
    assert has_augment(augment)
    detail = apply_augment_etb(game.zones, augment, game.zones.battlefield)
    assert detail is not None
    assert host.counters.get('+1/+1', 0) >= 3
    assert augment not in game.zones.battlefield
    assert augment.source in game.zones.player_zones[0].exile


def test_augment_etb_hook_runs_from_registry():
    """Augment is wired through apply_etb_other_abilities."""
    game = fresh_game()
    place_on_battlefield(make_creature('Host', 2, 2), 0, game.zones)
    augment = place_on_battlefield(
        make_creature('Augmenter', 2, 2, oracle='Augment'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, augment)
    assert any('augment' in line for line in details)
