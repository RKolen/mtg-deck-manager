"""Unit tests for keyword actions batch 4.

Tap, Untap, Sacrifice, Attach, Suspect, and Incubate.
"""

from __future__ import annotations

from engine.abilities.keywords.actions.board import (
    has_sacrifice_action,
    has_tap_action,
    has_untap_action,
    sacrifice_creature,
    tap_creature,
    untap_creature,
)
from engine.abilities.keywords.actions.specialty import (
    attach_to_creature,
    has_attach,
    has_incubate,
    has_suspect,
    incubate,
    suspect_creature,
)
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_card,
    make_creature,
    place_on_battlefield,
)


def test_tap_action_taps_target_creature():
    """Tap keyword action taps the chosen creature."""
    game = fresh_game()
    sentinel = place_on_battlefield(make_creature('Sentinel', 2, 3), 0, game.zones)
    oracle = 'Tap target creature.'
    assert has_tap_action(oracle)
    detail = tap_creature(game.zones, str(sentinel.obj_id))
    assert detail is not None
    assert sentinel.tapped


def test_untap_action_untaps_tapped_creature():
    """Untap keyword action clears the tapped state."""
    game = fresh_game()
    vine = place_on_battlefield(make_creature('Vine', 1, 1), 0, game.zones)
    vine.tapped = True
    oracle = 'Untap target creature.'
    assert has_untap_action(oracle)
    detail = untap_creature(game.zones, str(vine.obj_id))
    assert detail is not None
    assert not vine.tapped


def test_sacrifice_action_moves_creature_to_graveyard():
    """Sacrifice keyword action puts the creature in the graveyard."""
    game = fresh_game()
    offering = place_on_battlefield(make_creature('Offering', 2, 2), 0, game.zones)
    oracle = 'Sacrifice target creature.'
    assert has_sacrifice_action(oracle)
    detail = sacrifice_creature(game.zones, game, str(offering.obj_id))
    assert detail is not None
    assert game.zones.find_permanent(offering.obj_id) is None
    assert len(game.zones.player_zones[0].graveyard) == 1


def test_attach_links_equipment_to_creature_host():
    """Attach keyword action equips an artifact to a creature."""
    game = fresh_game()
    sword = place_on_battlefield(
        make_card(
            'Sword',
            type_line='Artifact — Equipment',
            oracle='Equip {2}',
            stats=_CardStats(cmc=2.0),
        ),
        0,
        game.zones,
    )
    knight = place_on_battlefield(make_creature('Knight', 3, 3), 0, game.zones)
    assert has_attach('Attach.')
    detail = attach_to_creature(game.zones, str(sword.obj_id), str(knight.obj_id))
    assert detail is not None
    assert sword.attached_to == knight.obj_id


def test_suspect_marks_creature_for_combat_rules():
    """Suspect marks a creature with the suspect counter."""
    game = fresh_game()
    rogue = place_on_battlefield(make_creature('Rogue', 2, 1), 1, game.zones)
    assert has_suspect('Suspect.')
    detail = suspect_creature(game.zones, str(rogue.obj_id))
    assert detail is not None
    assert rogue.counters.get('suspect') == 1


def test_incubate_creates_incubator_with_counters():
    """Incubate creates an incubator token with +1/+1 counters."""
    game = fresh_game()
    oracle = 'Incubate 2.'
    assert has_incubate(oracle)
    detail = incubate(game.zones, 0, oracle)
    assert 'incubated' in detail
    incubators = [
        perm for perm in game.zones.battlefield
        if perm.controller_idx == 0 and 'Incubator' in perm.type_line
    ]
    assert len(incubators) == 1
    assert incubators[0].counters.get('+1/+1') == 2
