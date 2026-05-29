"""Unit tests for ability_other batch 10: craft, companion, offspring, decayed, enlist, dethrone."""

from __future__ import annotations

from engine.abilities.keywords.combat import can_attack
from engine.abilities.keywords.other.companion import (
    find_companion_in_deck,
    validate_companion_deck,
)
from engine.abilities.keywords.other.craft import apply_craft, craft_artifact_error
from engine.abilities.keywords.other.decayed import (
    apply_decayed_etb,
    sacrifice_decayed_creatures,
)
from engine.abilities.keywords.other.dethrone import (
    apply_dethrone_on_combat_damage_to_player,
)
from engine.abilities.keywords.other.enlist import apply_enlist_on_attack
from engine.abilities.keywords.other.offspring import apply_offspring_etb
from tests.conftest import (
    fresh_game,
    make_artifact,
    make_creature,
    place_on_battlefield,
    resolve_player_attacks,
)

_COMPANION_ORACLE = (
    'Companion — Your deck contains only creature cards, '
    'each with mana value 3 or greater.'
)
_CRAFT_ORACLE = (
    '{2}, Exile three artifacts you control: Craft this artifact '
    'into a creature.'
)


def test_companion_validates_creature_deck():
    """Companion accepts decks that satisfy the restriction."""
    companion = make_creature(
        'Lurrus',
        3,
        3,
        cmc=3,
        oracle=_COMPANION_ORACLE,
    )
    deck = [
        companion,
        make_creature('Bear', 3, 3, cmc=3),
        make_creature('Elf', 4, 4, cmc=4),
    ]
    assert find_companion_in_deck(deck) is companion
    assert validate_companion_deck(deck) is None


def test_companion_rejects_low_cmc_creature():
    """Companion rejects decks with creatures below the mana value floor."""
    companion = make_creature(
        'Lurrus',
        3,
        3,
        cmc=3,
        oracle=_COMPANION_ORACLE,
    )
    deck = [companion, make_creature('Cheap', 1, 1, cmc=1)]
    assert validate_companion_deck(deck) is not None


def test_craft_exiles_artifacts_and_marks_crafted():
    """Craft exiles artifacts and marks the host permanent crafted."""
    game = fresh_game()
    host = place_on_battlefield(
        make_artifact('Clay', oracle=_CRAFT_ORACLE),
        0,
        game.zones,
    )
    relic = place_on_battlefield(make_artifact('Relic'), 0, game.zones)
    assert craft_artifact_error(game, host, 0, [relic.obj_id]) is None
    detail = apply_craft(game, host, [relic.obj_id])
    assert detail
    assert host.counters.get('crafted') == 1
    assert len(game.zones.player_zones[0].exile) == 1


def test_offspring_creates_token_on_etb():
    """Offspring creates a token copy when the creature enters."""
    game = fresh_game()
    parent = place_on_battlefield(
        make_creature('Parent', 2, 3, oracle='Offspring {2}'),
        0,
        game.zones,
    )
    detail = apply_offspring_etb(game.zones, parent)
    assert detail
    tokens = [p for p in game.zones.battlefield if p.is_token]
    assert len(tokens) == 1
    assert tokens[0].name == 'Parent Token'


def test_decayed_cannot_attack_and_sacrifices_at_eot():
    """Decayed creatures cannot attack and are sacrificed at end of turn."""
    game = fresh_game()
    zombie = place_on_battlefield(
        make_creature('Zombie', 2, 2, oracle='Decayed'),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_decayed_etb(zombie)
    assert detail is not None
    assert 'decayed' in detail.lower()
    assert not can_attack(zombie)
    sacrifice_decayed_creatures(game, 0)
    assert len(game.zones.battlefield) == 0


def test_enlist_taps_helper_creature():
    """Enlist taps a non-attacking creature when the attacker has enlist."""
    game = fresh_game()
    helper = place_on_battlefield(make_creature('Helper', 1, 1), 0, game.zones)
    attacker = place_on_battlefield(
        make_creature('Enlister', 3, 3, oracle='Enlist'),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_enlist_on_attack(
        game,
        attacker,
        [str(attacker.obj_id)],
    )
    assert detail
    assert helper.tapped


def test_dethrone_on_damage_to_leading_player():
    """Dethrone triggers when the damaged player has the most life."""
    game = fresh_game()
    game.players[0].life = 15
    game.players[1].life = 20
    attacker = place_on_battlefield(
        make_creature('Regent', 2, 2, oracle='Dethrone'),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_dethrone_on_combat_damage_to_player(
        game,
        attacker,
        2,
        damaged_player_idx=1,
    )
    assert detail
    resolve_player_attacks(game, attacker)
