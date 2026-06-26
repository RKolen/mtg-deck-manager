"""Unit tests for aura swap, banding, double team, enchant, and firebending (batch 31)."""

from __future__ import annotations

from engine.abilities.keywords.combat import can_attack
from engine.abilities.keywords.other.aura_swap import apply_aura_swap, has_aura_swap
from engine.abilities.keywords.other.banding import (
    attacking_band_size,
    banding_block_detail,
    has_banding,
)
from engine.abilities.keywords.other.double_team import (
    apply_double_team_on_attack,
    has_double_team,
)
from engine.abilities.keywords.other.enchant import can_enchant_target, has_enchant
from engine.abilities.keywords.other.firebending import (
    apply_firebending_on_attack,
    clear_firebending_mana,
    has_firebending,
)
from engine.core.game_object import CardObject
from tests.conftest import _CardStats, fresh_game, make_card, make_creature, place_on_battlefield


def test_aura_swap_exchanges_auras():
    """Aura swap moves the battlefield Aura to hand and plays one from hand."""
    game = fresh_game()
    host = place_on_battlefield(make_creature('Bearer', 2, 2), 0, game.zones)
    old_aura = place_on_battlefield(
        make_card(
            name='Old Shield',
            type_line='Enchantment — Aura',
            oracle='Aura swap {1}{W}\nEnchant creature',
            mana_cost='{W}',
            stats=_CardStats(cmc=1.0, pt='0/0'),
        ),
        0,
        game.zones,
    )
    old_aura.attached_to = host.obj_id
    new_aura_card = CardObject(
        controller_idx=0,
        owner_idx=0,
        card_info=make_card(
            name='New Shield',
            type_line='Enchantment — Aura',
            oracle='Enchant creature',
            mana_cost='{W}',
            stats=_CardStats(cmc=1.0, pt='0/0'),
        ),
    )
    game.zones.player_zones[0].hand.append(new_aura_card)
    assert has_aura_swap(old_aura)
    detail = apply_aura_swap(game, old_aura, 0)
    assert detail is not None
    hand_names = [
        c.card_info.name
        for c in game.zones.player_zones[0].hand
        if isinstance(c, CardObject) and c.card_info is not None
    ]
    assert 'Old Shield' in hand_names
    assert game.zones.battlefield[-1].name == 'New Shield'
    assert game.zones.battlefield[-1].attached_to == host.obj_id


def test_banding_logs_block_assignment():
    """Banding blockers let the defender assign damage."""
    blocker = make_creature('Defender', 2, 2, oracle='Banding')
    attacker = make_creature('Raider', 3, 3)
    game = fresh_game()
    blocker_perm = place_on_battlefield(blocker, 0, game.zones)
    attacker_perm = place_on_battlefield(attacker, 1, game.zones)
    assert has_banding(blocker_perm)
    detail = banding_block_detail(blocker_perm, attacker_perm)
    assert detail is not None
    assert 'banding' in detail


def test_double_team_conjures_duplicate():
    """Double team puts a duplicate in hand and removes the ability."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Beetles', 2, 3, oracle='Double team'),
        0,
        game.zones,
    )
    assert has_double_team(perm)
    detail = apply_double_team_on_attack(game, perm)
    assert detail is not None
    assert len(game.zones.player_zones[0].hand) == 1
    assert perm.counters.get('double_team_lost', 0) == 1


def test_enchant_validates_aura_targets():
    """Enchant checks whether a host is a legal aura target."""
    creature = make_creature('Bear', 2, 2)
    land = make_card(
        name='Forest',
        type_line='Basic Land — Forest',
        oracle='',
        mana_cost='',
        stats=_CardStats(cmc=0.0, pt='0/0'),
    )
    game = fresh_game()
    host_creature = place_on_battlefield(creature, 0, game.zones)
    host_land = place_on_battlefield(land, 0, game.zones)
    aura = make_card(
        name='Pacifism',
        type_line='Enchantment — Aura',
        oracle='Enchant creature',
        mana_cost='{1}{W}',
        stats=_CardStats(cmc=2.0, pt='0/0'),
    )
    assert has_enchant(aura)
    assert can_enchant_target(aura.oracle_text, host_creature)
    assert not can_enchant_target(aura.oracle_text, host_land)


def test_firebending_adds_red_mana_until_combat_ends():
    """Firebending adds red mana that is cleared after combat."""
    game = fresh_game()
    sage = place_on_battlefield(
        make_creature('Fire Sages', 2, 2, oracle='Firebending 2'),
        0,
        game.zones,
    )
    assert has_firebending(sage)
    detail = apply_firebending_on_attack(game, sage)
    assert detail is not None
    assert game.players[0].mana_pool.of_color('R') == 2
    cleared = clear_firebending_mana(game, 0)
    assert cleared
    assert game.players[0].mana_pool.of_color('R') == 0


def test_banding_band_size_with_multiple_attackers():
    """Two banding attackers form a band."""
    game = fresh_game()
    first = place_on_battlefield(make_creature('Band A', 2, 2, oracle='Banding'), 0, game.zones)
    second = place_on_battlefield(make_creature('Band B', 2, 2, oracle='Banding'), 0, game.zones)
    assert attacking_band_size([first, second]) == 2
    assert can_attack(first, game)
