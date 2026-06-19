"""Unit tests for sunburst, unleash, vanishing, rampage, and skulk (batch 24)."""

from __future__ import annotations

from engine.abilities.keywords.combat import can_block, legal_blocker
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.rampage import apply_rampage_on_block, has_rampage
from engine.abilities.keywords.other.skulk import has_skulk, skulk_allows_block
from engine.abilities.keywords.other.sunburst import apply_sunburst_etb, has_sunburst
from engine.abilities.keywords.other.unleash import (
    apply_unleash_etb,
    has_unleash,
    unleash_prevents_block,
)
from engine.abilities.keywords.other.vanishing import (
    apply_vanishing_etb,
    resolve_vanishing_upkeep,
)
from engine.core.mana import mana_of
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_sunburst_counts_colors_in_mana_pool():
    """Sunburst puts +1/+1 counters for each color in the mana pool."""
    game = fresh_game()
    game.players[0].mana_pool.add(mana_of('R'), mana_of('U'))
    perm = place_on_battlefield(
        make_creature('Core', 0, 0, oracle='Sunburst'),
        0,
        game.zones,
    )
    assert has_sunburst(perm)
    detail = apply_sunburst_etb(game, perm)
    assert detail is not None
    assert perm.counters.get('+1/+1', 0) == 2


def test_unleash_puts_counter_and_prevents_blocking():
    """Unleash gives +1/+1 and prevents blocking."""
    perm = place_on_battlefield(
        make_creature('Brawler', 2, 2, oracle='Unleash'),
        0,
        fresh_game().zones,
    )
    assert has_unleash(perm)
    detail = apply_unleash_etb(perm)
    assert detail is not None
    assert perm.counters.get('+1/+1', 0) == 1
    assert unleash_prevents_block(perm)
    assert not can_block(perm)


def test_vanishing_sacrifices_at_zero_time():
    """Vanishing sacrifices the permanent when time counters reach zero."""
    game = fresh_game()
    perm = place_on_battlefield(
        make_creature('Flicker', 2, 2, oracle='Vanishing 1'),
        0,
        game.zones,
    )
    apply_vanishing_etb(perm)
    details = resolve_vanishing_upkeep(game, 0)
    assert any('sacrificed' in line for line in details)
    assert len(game.zones.battlefield) == 0


def test_rampage_buffs_when_blocked_by_two():
    """Rampage puts counters on the attacker when blocked twice."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Beast', 3, 3, oracle='Rampage 2'),
        0,
        game.zones,
    )
    blocker_a = place_on_battlefield(make_creature('Guard A', 1, 1), 1, game.zones)
    blocker_b = place_on_battlefield(make_creature('Guard B', 1, 1), 1, game.zones)
    assert has_rampage(attacker)
    detail = apply_rampage_on_block(attacker, [blocker_a, blocker_b])
    assert detail is not None
    assert attacker.counters.get('+1/+1', 0) == 2


def test_skulk_blocks_higher_power_blockers():
    """Skulk only allows blockers with equal or greater power."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Stalker', 3, 3, oracle='Skulk'),
        0,
        game.zones,
    )
    weak_blocker = place_on_battlefield(make_creature('Child', 1, 1), 1, game.zones)
    strong_blocker = place_on_battlefield(make_creature('Giant', 4, 4), 1, game.zones)
    assert has_skulk(attacker)
    assert not skulk_allows_block(weak_blocker, attacker)
    assert skulk_allows_block(strong_blocker, attacker)
    assert not legal_blocker(weak_blocker, attacker, game)
    assert legal_blocker(strong_blocker, attacker, game)


def test_sunburst_etb_hook_runs_from_registry():
    """Sunburst is wired through apply_etb_other_abilities."""
    game = fresh_game()
    game.players[0].mana_pool.add(mana_of('G'))
    perm = place_on_battlefield(
        make_creature('Seed', 1, 1, oracle='Sunburst'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, perm)
    assert any('sunburst' in line for line in details)
