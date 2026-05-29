"""Unit tests for ability_other batch 4: afflict, absorb, embalm."""

from __future__ import annotations

from engine.abilities.keywords.casting.embalm import create_embalm_token_in_exile
from engine.abilities.keywords.handlers import apply_combat_damage_to_creature
from engine.abilities.keywords.other.afflict import apply_afflict_on_attack
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_afflict_drains_on_attack():
    """Afflict reduces the defending player's life on attack."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Cruel', 3, 3, oracle='Afflict 1'),
        0,
        game.zones,
        sick=False,
    )
    apply_afflict_on_attack(game, attacker)
    assert game.players[1].life == 19


def test_absorb_reduces_combat_damage():
    """Absorb prevents damage marked on the permanent."""
    game = fresh_game()
    wall = place_on_battlefield(
        make_creature('Lymph Sliver', 1, 4, oracle='Absorb 1'),
        0,
        game.zones,
    )
    attacker = place_on_battlefield(make_creature('Goblin', 2, 2), 1, game.zones)
    apply_combat_damage_to_creature(wall, attacker, 2)
    assert wall.damage_marked == 1


def test_embalm_puts_token_in_exile():
    """Embalm creates a token in exile."""
    game = fresh_game()
    honored = make_creature('Honored', 4, 4, oracle='Embalm {3}{W}')
    detail = create_embalm_token_in_exile(game.zones, 0, honored)
    assert 'embalmed' in detail
    assert len(game.zones.player_zones[0].exile) == 1
