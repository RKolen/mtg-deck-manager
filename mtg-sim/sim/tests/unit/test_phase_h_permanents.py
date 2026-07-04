"""Tests for Phase H aura/planeswalker entry and loyalty abilities."""

from __future__ import annotations

from engine.abilities import activated
from engine.cards.permanent_entry import apply_planeswalker_entry, starting_loyalty
from engine.core.game_object import CardObject
from engine.game import create_game
from tests.conftest import _CardStats, make_card, make_creature, make_deck
from tests.conftest import make_land, place_on_battlefield


def test_starting_loyalty_parses_oracle_text():
    """Planeswalker loyalty is parsed from the enters-the-battlefield clause."""
    text = 'Jace enters the battlefield with three loyalty counters.\n+1: Draw a card.'
    assert starting_loyalty(text) == 3


def test_cast_aura_attaches_to_creature():
    """An Aura spell resolves attached to its enchant target."""
    pacifism = make_card(
        'Pacifism',
        type_line='Enchantment — Aura',
        oracle='Enchant creature\nEnchanted creature cannot attack or block.',
        mana_cost='{1}{W}',
        stats=_CardStats(cmc=2.0, pt='0/0'),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    host = place_on_battlefield(make_creature('Soldier', 2, 2), 0, game.state.zones, sick=False)
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=pacifism),
    ]
    place_on_battlefield(make_land('Plains', 'W'), 0, game.state.zones)
    place_on_battlefield(make_land('Plains', 'W'), 0, game.state.zones)
    data = game.action_cast(0, target_uid=str(host.obj_id))
    assert 'error' not in data
    aura = next(
        perm for perm in game.state.zones.battlefield
        if perm.name == 'Pacifism'
    )
    assert aura.attached_to == host.obj_id


def test_cast_aura_requires_target():
    """Casting an Aura without a target is rejected at announcement."""
    pacifism = make_card(
        'Pacifism',
        type_line='Enchantment — Aura',
        oracle='Enchant creature',
        mana_cost='{1}{W}',
        stats=_CardStats(cmc=2.0, pt='0/0'),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=pacifism),
    ]
    place_on_battlefield(make_land('Plains', 'W'), 0, game.state.zones)
    place_on_battlefield(make_land('Plains', 'W'), 0, game.state.zones)
    data = game.action_cast(0)
    assert 'error' in data


def test_cast_planeswalker_enters_with_loyalty():
    """A planeswalker spell enters with loyalty counters from its oracle text."""
    jace = make_card(
        'Jace, the Mind Sculptor',
        type_line='Legendary Planeswalker — Jace',
        oracle=(
            'Jace, the Mind Sculptor enters the battlefield with three loyalty counters.\n'
            '+1: Draw a card.'
        ),
        mana_cost='{2}{U}{U}',
        stats=_CardStats(cmc=4.0, pt='0/0'),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.zones.player_zones[0].hand = [
        CardObject(controller_idx=0, owner_idx=0, card_info=jace),
    ]
    for _ in range(4):
        place_on_battlefield(make_land('Island', 'U'), 0, game.state.zones)
    data = game.action_cast(0)
    assert 'error' not in data
    walker = next(
        perm for perm in game.state.zones.battlefield
        if 'Jace' in perm.name
    )
    assert walker.counters.get('loyalty') == 3


def test_planeswalker_loyalty_ability_changes_counters():
    """Activating +1 on a planeswalker adds a loyalty counter."""
    jace = make_card(
        'Jace Walker',
        type_line='Legendary Planeswalker — Jace',
        oracle='+1: Draw a card.\n-2: Draw two cards.',
        stats=_CardStats(cmc=4.0, pt='0/0'),
    )
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    walker_perm = place_on_battlefield(jace, 0, game.state.zones, sick=False)
    apply_planeswalker_entry(walker_perm)
    walker_perm.counters['loyalty'] = 3
    specs = activated.parse_activated_abilities(walker_perm.oracle_text)
    assert activated.loyalty_cost_change(specs[0].cost_text) == 1
    data = game.action_activate(str(walker_perm.obj_id), 0)
    assert 'error' not in data
    assert walker_perm.counters.get('loyalty') == 4


def test_mana_pool_client_payload_includes_colors():
    """Client payload exposes colored mana pool breakdown."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.players[0].mana_pool.add_color('R', 2)
    data = game.to_client()
    assert data['playerManaPool'] == {'total': 2, 'W': 0, 'U': 0, 'B': 0, 'R': 2, 'G': 0, 'C': 0}


def test_end_turn_empties_mana_pool():
    """Floating mana is drained when the player ends their turn."""
    game = create_game(make_deck(lands=20), make_deck(lands=20))
    game.action_keep()
    game.state.players[0].mana_pool.add_color('G', 1)
    game.action_end_turn()
    assert game.state.players[0].mana_pool.total() == 0
