"""Unit tests for ability_other batch 7: affinity cast path, renown, myriad."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.other.myriad import apply_myriad_on_attack
from engine.abilities.keywords.other.renown import (
    apply_renown_on_combat_damage_to_player,
    is_renowned,
)
from engine.core.game_state import GameState, PlayerInfo
from engine.core.turn_structure import TurnRunner
from engine.core.zones import ZoneManager
from engine.rules.combat import resolve_combat_damage
from engine.rules.stack import Stack
from tests.conftest import fresh_game, make_artifact, make_card, make_creature, place_on_battlefield

_AFFINITY_ORACLE = (
    'Affinity for artifacts (This spell costs {1} less to cast for each '
    'artifact you control.)'
)


def _affinity_card():
    return make_card(
        'Frogmite',
        cmc=4.0,
        mana_cost='{4}',
        oracle=_AFFINITY_ORACLE,
    )


def test_resolve_announce_cast_mana_applies_affinity():
    """Hand-cast mana resolution includes artifact affinity discounts."""
    game = fresh_game()
    card = _affinity_card()
    for _ in range(2):
        place_on_battlefield(make_artifact('Vault', oracle=''), 0, game.zones)
    mana_needed, _life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(zones=game.zones, controller_idx=0),
    )
    assert mana_needed == 2


def test_renown_puts_counter_on_player_damage():
    """Renown triggers when the creature deals combat damage to a player."""
    game = fresh_game()
    renowned_creature = place_on_battlefield(
        make_creature('Renown Knight', 2, 2, oracle='Renown'),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_renown_on_combat_damage_to_player(renowned_creature, 2)
    assert detail
    assert renowned_creature.counters.get('+1/+1') == 1
    assert is_renowned(renowned_creature)
    assert apply_renown_on_combat_damage_to_player(renowned_creature, 1) is None


def test_renown_via_combat_damage():
    """Renown applies during unblocked combat damage resolution."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Renown Raider', 3, 3, oracle='Renown'),
        0,
        game.zones,
        sick=False,
    )
    resolve_combat_damage(
        game,
        attacking_player_idx=0,
        defending_player_idx=1,
        attacker_ids=[str(attacker.obj_id)],
        blocker_assignments={},
    )
    assert is_renowned(attacker)
    assert attacker.counters.get('+1/+1') == 1


def test_myriad_skips_only_opponent_in_two_player_game():
    """Myriad creates no tokens when the only opponent is the defender."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Myriad Beast', 2, 2, oracle='Myriad'),
        0,
        game.zones,
        sick=False,
    )
    before = len(game.zones.battlefield)
    assert apply_myriad_on_attack(game, attacker, defending_player_idx=1) is None
    assert len(game.zones.battlefield) == before


def test_myriad_creates_token_for_other_opponent():
    """Myriad creates a token copy attacking each non-defending opponent."""
    zones = ZoneManager()
    game = GameState(
        game_id='three-player',
        zones=zones,
        players=[PlayerInfo('p0'), PlayerInfo('p1'), PlayerInfo('p2')],
        turn=TurnRunner(),
        stack=Stack(),
    )
    attacker = place_on_battlefield(
        make_creature('Myriad Host', 4, 4, oracle='Myriad'),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_myriad_on_attack(game, attacker, defending_player_idx=1)
    assert detail
    tokens = [p for p in game.zones.battlefield if p.is_token]
    assert len(tokens) == 1
    assert tokens[0].name == 'Myriad Host'
    assert tokens[0].tapped
    assert tokens[0].counters.get('myriad_attacking') == 3
