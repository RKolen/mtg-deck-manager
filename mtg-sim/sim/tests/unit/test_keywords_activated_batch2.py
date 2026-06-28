"""Unit tests for activated batch 2: scavenge, bloodrush, equip, mana abilities."""

from __future__ import annotations

from engine.abilities.activated.bloodrush import (
    bloodrush_mana_needed,
    bloodrush_power,
    has_bloodrush_card,
)
from engine.abilities.activated.card_keyword_abilities import (
    can_scavenge,
    has_scavenge_card,
    scavenge_counter_amount,
    scavenge_from_graveyard,
    scavenge_mana_needed,
)
from engine.abilities.activated.core import (
    ActivationSpeed,
    activate_equip,
    activate_mana_ability,
    activatable_ability_indices,
    equip_mana_needed,
    has_equip_card,
    has_mana_ability_card,
    parse_activated_abilities,
)
from engine.core.game_object import CardObject
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_card,
    make_creature,
    place_on_battlefield,
)


def test_scavenge_card_exiles_creature_for_counters():
    """Scavenge card detection and +1/+1 counters from power."""
    game = fresh_game()
    scavenger = make_creature('Snap', 3, 2, oracle='Scavenge {2}{G}')
    assert has_scavenge_card(scavenger)
    assert scavenge_mana_needed(scavenger) == 3
    assert scavenge_counter_amount(scavenger) == 3
    game.zones.player_zones[0].graveyard = [
        CardObject(controller_idx=0, owner_idx=0, card_info=scavenger),
    ]
    target = place_on_battlefield(make_creature('Bear', 2, 2), 0, game.zones)
    err, detail = scavenge_from_graveyard(game.zones, 0, 0, target)
    assert err is None
    assert detail is not None
    assert target.counters.get('+1/+1') == 3


def test_scavenge_card_allows_main_phase_activation():
    """Scavenge card detection and graveyard activation timing."""
    creature = make_creature('Vorapede', 5, 4, oracle='Scavenge {3}{G}{G}')
    assert has_scavenge_card(creature)
    assert can_scavenge(creature, 'main1', stack_is_empty=True)
    assert not can_scavenge(creature, 'attack', stack_is_empty=True)


def test_bloodrush_card_parses_creature_pump_cost():
    """Bloodrush card detection and power granted from the discarded card."""
    card = make_creature(
        'Ghor-Clan',
        4,
        4,
        oracle='Bloodrush — {R}, Discard Ghor-Clan Rampager: Target creature gets +4/+0.',
    )
    assert has_bloodrush_card(card)
    assert bloodrush_mana_needed(card) == 1
    assert bloodrush_power(card) == 4


def test_equip_card_detects_equipment_ability():
    """Equip card detection and mana for the equip activation."""
    sword = make_card(
        'Sword',
        type_line='Artifact — Equipment',
        oracle='Equipped creature gets +2/+2.\nEquip {2}',
        stats=_CardStats(cmc=2.0),
    )
    assert has_equip_card(sword)
    assert equip_mana_needed(sword) == 2
    assert not has_equip_card(make_creature('Knight', 2, 2))


def test_equip_activation_attaches_to_creature_host():
    """Equip activation attaches equipment to a legal creature host."""
    game = fresh_game()
    sword = place_on_battlefield(
        make_card(
            'Blade',
            type_line='Artifact — Equipment',
            oracle='Equip {1}',
            stats=_CardStats(cmc=1.0),
        ),
        0,
        game.zones,
    )
    host = place_on_battlefield(make_creature('Soldier', 2, 2), 0, game.zones)
    spec = parse_activated_abilities(sword.oracle_text)[0]
    result = activate_equip(game, sword, host, spec)
    assert result.ok
    assert sword.attached_to == host.obj_id


def test_mana_ability_card_taps_land_for_mana():
    """Mana ability card detection and immediate mana resolution."""
    game = fresh_game()
    forest_card = make_card(
        name='Forest',
        type_line='Basic Land — Forest',
        oracle='{T}: Add {G}.',
        stats=_CardStats(cmc=0.0),
    )
    assert has_mana_ability_card(forest_card)
    forest = place_on_battlefield(forest_card, 0, game.zones)
    spec = parse_activated_abilities(forest.oracle_text)[0]
    indices = activatable_ability_indices(
        forest,
        game,
        0,
        ActivationSpeed.INSTANT,
    )
    assert indices == [0]
    detail = activate_mana_ability(game, forest, spec)
    assert 'added' in detail.lower()
    assert forest.tapped
