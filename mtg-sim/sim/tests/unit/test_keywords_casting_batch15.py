"""Unit tests for convoke/delve/improvise/emerge hand flags (batch 15)."""

from __future__ import annotations

from engine.game.helpers import card_to_client
from tests.conftest import make_creature, make_instant


def test_card_to_client_cast_modifier_flags():
    """Hand cards expose convoke, delve, improvise, and emerge for the play UI."""
    convoke = card_to_client(0, make_instant('Justice', oracle='Deal 4 damage. Convoke'), 10)
    delve = card_to_client(0, make_instant('Cruise', oracle='Draw three cards. Delve'), 10)
    improvise = card_to_client(0, make_instant('Order', oracle='Draw a card. Improvise'), 10)
    emerge = card_to_client(
        0,
        make_creature('Wurm', 7, 7, oracle='Emerge {6}{G}\nTrample'),
        10,
    )
    assert convoke['hasConvoke'] is True
    assert convoke['hasDelve'] is False
    assert delve['hasDelve'] is True
    assert improvise['hasImprovise'] is True
    assert emerge['hasEmerge'] is True
    assert emerge['hasConvoke'] is False
