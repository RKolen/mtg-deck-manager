"""Unit tests for multikicker (batch 34)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaModifiers,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.casting.kicker import (
    kicked_counter_count,
    normalize_kicker_times,
)
from engine.abilities.keywords.other.multikicker import has_multikicker
from tests.conftest import make_instant


def test_multikicker_paid_multiple_times():
    """Multikicker allows paying the kicker cost more than once."""
    card = make_instant(
        'Strength',
        oracle='Multikicker {1}\nDraw a card.',
        mana_cost='{2}',
    )
    assert has_multikicker(card)
    assert normalize_kicker_times(card, 3) == 3
    paid_mana, _life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            modifiers=CastManaModifiers(kicker_times=3),
        ),
    )
    assert paid_mana == 5
    assert kicked_counter_count(card, 3) == 3
