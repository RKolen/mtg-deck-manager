"""Unit tests for jump-start, retrace, and aftermath (batch 14)."""

from __future__ import annotations

from engine.abilities.keywords.casting.aftermath import can_cast_aftermath, has_aftermath
from engine.abilities.keywords.casting.jump_start import (
    can_cast_via_jump_start,
    discard_for_jump_start,
    has_jump_start,
)
from engine.abilities.keywords.casting.retrace import (
    can_cast_via_retrace,
    discard_land_for_retrace,
    has_retrace,
)
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_card, make_creature, make_instant, make_land


def test_jump_start_discards_from_hand():
    """Jump-start exiles a spell from the graveyard after discarding from hand."""
    game = fresh_game()
    zones = game.zones
    gy_card = make_instant('Mission', oracle='Jump-start {2}{U}\nDraw two cards.')
    zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=gy_card),
    )
    hand_card = make_creature('Toss', 1, 1)
    zones.player_zones[0].hand.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=hand_card),
    )
    assert has_jump_start(gy_card)
    assert can_cast_via_jump_start(gy_card, 'main1', True)
    discarded = discard_for_jump_start(zones, 0, 0)
    assert discarded.card_info is not None
    assert discarded.card_info.name == 'Toss'
    assert len(zones.player_zones[0].hand) == 0
    assert len(zones.player_zones[0].graveyard) == 2


def test_retrace_requires_land_discard():
    """Retrace discards a land from hand to cast from the graveyard."""
    game = fresh_game()
    zones = game.zones
    gy_card = make_instant('Loam', oracle='Retrace\nReturn target land.')
    zones.player_zones[0].graveyard.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=gy_card),
    )
    zones.player_zones[0].hand.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=make_land('Forest')),
    )
    assert has_retrace(gy_card)
    assert can_cast_via_retrace(gy_card, 'main1', True)
    discard_land_for_retrace(zones, 0, 0)
    assert len(zones.player_zones[0].hand) == 0
    assert len(zones.player_zones[0].graveyard) == 2


def test_aftermath_main_phase_only():
    """Aftermath may only be cast from the graveyard on an empty stack main phase."""
    card = make_card(
        'Reduce',
        type_line='Sorcery',
        oracle='Aftermath\nExile target creature.',
    )
    assert has_aftermath(card)
    assert can_cast_aftermath(card, 'main1', True)
    assert not can_cast_aftermath(card, 'attack', True)
