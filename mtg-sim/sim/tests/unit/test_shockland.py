"""Unit tests for shockland ETB detection."""

from __future__ import annotations

from engine.abilities.keywords.other.shockland import has_shockland_etb
from tests.conftest import make_card, make_land


def test_has_shockland_etb_detects_steam_vents():
    """Steam Vents matches the pay-2-life-or-tapped pattern."""
    card = make_card(
        name='Steam Vents',
        type_line='Land — Island Mountain',
        oracle=(
            'As Steam Vents enters the battlefield, you may pay 2 life. '
            "If you don't, it enters the battlefield tapped."
        ),
    )
    assert has_shockland_etb(card) is True


def test_has_shockland_etb_rejects_basic_land():
    """Basic lands do not use the shockland ETB pattern."""
    assert has_shockland_etb(make_land('Island', 'U')) is False
