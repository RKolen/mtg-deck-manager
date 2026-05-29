"""
Unit tests for ability_other batch 11:
bushido, outlast, mobilize, disturb, eternalize, encore EOT.
"""

from __future__ import annotations

from engine.abilities.keywords.casting.disturb import (
    disturb_mana_needed,
    has_disturb,
)
from engine.abilities.keywords.other.bushido import apply_bushido_when_engaged
from engine.abilities.keywords.other.encore import (
    apply_encore_from_graveyard,
    sacrifice_encore_tokens,
)
from engine.abilities.keywords.other.eternalize import apply_eternalize_from_graveyard
from engine.abilities.keywords.other.mobilize import apply_mobilize_on_attack
from engine.abilities.keywords.other.outlast import apply_outlast, can_outlast
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_creature, place_on_battlefield, resolve_player_attacks


def test_bushido_puts_counters_when_engaged():
    """Bushido grants +N/+N when the creature is engaged in combat."""
    game = fresh_game()
    samurai = place_on_battlefield(
        make_creature('Samurai', 2, 2, oracle='Bushido 2'),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_bushido_when_engaged(samurai)
    assert detail
    assert samurai.counters.get('+1/+1') == 2
    assert apply_bushido_when_engaged(samurai) is None


def test_outlast_puts_counter_once_per_turn():
    """Outlast adds +1/+1 and cannot be used again the same turn."""
    game = fresh_game()
    creature = place_on_battlefield(
        make_creature('Abzan', 1, 1, oracle='Outlast {1}{W}'),
        0,
        game.zones,
    )
    assert can_outlast(creature, game, 0, 'main1')
    detail = apply_outlast(creature)
    assert detail
    assert creature.counters.get('+1/+1') == 1
    assert not can_outlast(creature, game, 0, 'main1')


def test_mobilize_creates_soldiers_on_attack():
    """Mobilize creates Soldier tokens when attacking."""
    game = fresh_game()
    leader = place_on_battlefield(
        make_creature('Leader', 3, 3, oracle='Mobilize 2'),
        0,
        game.zones,
        sick=False,
    )
    detail = apply_mobilize_on_attack(game, leader)
    assert detail
    soldiers = [
        p for p in game.zones.battlefield
        if p.is_token and 'Soldier' in p.type_line
    ]
    assert len(soldiers) == 2


def test_disturb_parses_creature_graveyard_cost():
    """Disturb is recognized on creature cards with an alternate cost."""
    card = make_creature(
        'Grief',
        4,
        3,
        oracle='Disturb {1}{W}\nFlying',
    )
    assert has_disturb(card)
    assert disturb_mana_needed(card) == 2


def test_eternalize_creates_exile_token():
    """Eternalize exiles the card and creates a token in exile."""
    game = fresh_game()
    creature = make_creature('Honored', 4, 4, oracle='Eternalize {3}{W}')
    game.zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=creature),
    )
    detail = apply_eternalize_from_graveyard(game.zones, 0, 0)
    assert detail
    assert len(game.zones.player_zones[0].exile) == 2


def test_encore_tokens_sacrificed_at_end_step():
    """Encore tokens are sacrificed at end of turn."""
    game = fresh_game()
    creature = make_creature('Siege', 3, 3, oracle='Encore {2}{B}')
    game.zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=creature),
    )
    apply_encore_from_graveyard(game, game.zones, 0, 0)
    assert len(game.zones.battlefield) == 1
    details = sacrifice_encore_tokens(game, 0)
    assert details
    assert len(game.zones.battlefield) == 0


def test_bushido_in_blocked_combat():
    """Bushido applies during blocked combat damage."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Attacker', 3, 3),
        0,
        game.zones,
        sick=False,
    )
    blocker = place_on_battlefield(
        make_creature('Blocker', 2, 2, oracle='Bushido 1'),
        1,
        game.zones,
        sick=False,
    )
    resolve_player_attacks(
        game,
        attacker,
        blocker_assignments={str(blocker.obj_id): str(attacker.obj_id)},
    )
    assert blocker.counters.get('+1/+1') == 1
