"""
Unit tests for ability_other batch 12:
dredge, scavenge, craft transform, escape auto-exile.
"""

from __future__ import annotations

from engine.abilities.activated import card_keyword_abilities as scavenge
from engine.abilities.keywords.casting.escape import (
    auto_escape_exile_indices,
    escape_exiles_required,
)
from engine.abilities.keywords.other.craft import apply_craft, has_craft
from engine.abilities.keywords.other.dredge import apply_dredge, dredge_amount, has_dredge
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_artifact, make_creature, place_on_battlefield


def test_dredge_mills_from_library():
    """Dredge mills N cards and leaves the dredge card in the graveyard."""
    game = fresh_game()
    zones = game.zones
    lib = zones.player_zones[0].library
    for idx in range(5):
        card = make_creature(f'Lib{idx}', 1, 1)
        lib.append(CardObject(controller_idx=0, owner_idx=0, card_info=card))
    dredge_card = make_creature('Stinkweed', 6, 6, oracle='Dredge 3')
    zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=dredge_card),
    )
    assert has_dredge(dredge_card)
    assert dredge_amount(dredge_card) == 3
    lib_before = len(lib)
    gy_before = len(zones.player_zones[0].graveyard)
    err, detail, milled = apply_dredge(zones, 0, 0)
    assert err is None
    assert detail and 'milled 3' in detail
    assert len(milled) == 3
    assert len(lib) == lib_before - 3
    assert len(zones.player_zones[0].graveyard) == gy_before + 3


def test_scavenge_exiles_and_counters_target():
    """Scavenge exiles a graveyard creature and buffs a battlefield creature."""
    game = fresh_game()
    zones = game.zones
    gy_card = make_creature('Gravecrawler', 2, 2, oracle='Scavenge {B}')
    zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=gy_card),
    )
    target = place_on_battlefield(make_creature('Target', 1, 1), 0, zones)
    err, detail = scavenge.scavenge_from_graveyard(zones, 0, 0, target)
    assert err is None
    assert detail
    assert len(zones.player_zones[0].graveyard) == 0
    assert target.counters.get('+1/+1') == 2


def test_craft_transform_toggles_face_down():
    """Craft with transform in oracle toggles the crafted permanent face-down."""
    game = fresh_game()
    host = place_on_battlefield(
        make_creature(
            'Clay',
            2,
            2,
            oracle='Craft, {2}: Exile two artifacts you control. Transform this permanent.',
        ),
        0,
        game.zones,
    )
    art = place_on_battlefield(
        make_artifact('Token', oracle='Artifact'),
        0,
        game.zones,
    )
    assert has_craft(host)
    assert not host.face_down
    detail = apply_craft(game, host, [art.obj_id])
    assert detail
    assert host.counters.get('crafted') == 1
    assert host.face_down


def test_auto_escape_exile_indices_skips_spell():
    """Auto escape picks other graveyard cards, not the spell being cast."""
    game = fresh_game()
    zones = game.zones
    gy = zones.player_zones[0].graveyard
    for idx in range(5):
        card = make_creature(f'Card{idx}', 1, 1, oracle='Escape—{2}{B}, Exile four other cards')
        gy.append(CardObject(controller_idx=0, owner_idx=0, card_info=card))
    spell_raw = gy[2]
    assert isinstance(spell_raw, CardObject)
    assert spell_raw.card_info is not None
    spell_info = spell_raw.card_info
    required = escape_exiles_required(spell_info)
    picked = auto_escape_exile_indices(zones, 0, 2, spell_info)
    assert len(picked) == required
    assert 2 not in picked
