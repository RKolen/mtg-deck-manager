"""Unit tests for tribute, soulshift, provoke, poisonous, and recover (batch 25)."""

from __future__ import annotations

from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.poisonous import (
    apply_poisonous_on_player_damage,
    has_poisonous,
)
from engine.abilities.keywords.other.provoke import assign_provoke_blocks, has_provoke
from engine.abilities.keywords.other.recover import has_recover, resolve_recover_upkeep
from engine.abilities.keywords.other.soulshift import apply_soulshift_etb, has_soulshift
from engine.abilities.keywords.other.tribute import apply_tribute_etb, has_tribute
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_tribute_puts_counter_on_etb():
    """Tribute grants +1/+1 on enter."""
    perm = place_on_battlefield(
        make_creature('Hoarder', 2, 2, oracle='Tribute 2'),
        0,
        fresh_game().zones,
    )
    assert has_tribute(perm)
    detail = apply_tribute_etb(perm)
    assert detail is not None
    assert perm.counters.get('+1/+1', 0) == 1


def test_soulshift_returns_creature_from_graveyard():
    """Soulshift returns a creature card from the graveyard."""
    game = fresh_game()
    gy_card = make_creature('Spirit', 1, 1, mana_cost='{1}{B}')
    game.zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=gy_card),
    )
    perm = place_on_battlefield(
        make_creature('Shaman', 3, 2, oracle='Soulshift 2'),
        0,
        game.zones,
    )
    assert has_soulshift(perm)
    detail = apply_soulshift_etb(game, perm)
    assert detail is not None
    assert 'returned' in detail
    assert len(game.zones.player_zones[0].hand) == 1


def test_provoke_assigns_blocker():
    """Provoke forces a legal blocker when none was assigned."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Taunter', 2, 2, oracle='Provoke'),
        1,
        game.zones,
    )
    blocker = place_on_battlefield(make_creature('Guard', 2, 2), 0, game.zones)
    assert has_provoke(attacker)
    pending: dict[str, str] = {}
    details = assign_provoke_blocks(
        game,
        pending,
        [str(attacker.obj_id)],
        defending_player_idx=0,
    )
    assert details
    assert pending[str(blocker.obj_id)] == str(attacker.obj_id)


def test_poisonous_adds_poison_counters():
    """Poisonous gives poison counters when damage is dealt."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Viper', 1, 1, oracle='Poisonous 2'),
        0,
        game.zones,
    )
    assert has_poisonous(attacker)
    detail = apply_poisonous_on_player_damage(game, attacker, 2, 1)
    assert detail is not None
    assert game.players[1].poison == 2


def test_recover_returns_card_at_upkeep():
    """Recover returns a card from the graveyard at upkeep."""
    game = fresh_game()
    recover_card = make_instant('Renewal', cmc=3, oracle='Recover')
    assert has_recover(recover_card)
    game.zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=recover_card),
    )
    details = resolve_recover_upkeep(game, 0)
    assert details
    assert len(game.zones.player_zones[0].hand) == 1


def test_tribute_etb_hook_runs_from_registry():
    """Tribute is wired through apply_etb_other_abilities."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Tyrant', 4, 4, oracle='Tribute 3'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, perm)
    assert any('tribute' in line for line in details)
