"""Unit tests for More Than Meets the Eye (batch 32)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaTiming,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.casting.more_than_meets_the_eye import (
    apply_converted_on_etb,
    has_more_than_meets_the_eye,
    is_converted,
    normalize_more_than_meets_the_eye_cast,
    more_than_meets_the_eye_mana_needed,
)
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_more_than_meets_the_eye_alternate_cost_and_etb_marker():
    """Converted cast uses the alternate cost and marks the permanent."""
    card = make_creature(
        'Autobot Leader',
        4,
        4,
        oracle=(
            'More Than Meets the Eye {2}{U} '
            '(You may cast this card converted for {2}{U}.)'
        ),
        mana_cost='{4}{U}{U}',
    )
    assert has_more_than_meets_the_eye(card)
    assert normalize_more_than_meets_the_eye_cast(card, True)
    mana, _life = more_than_meets_the_eye_mana_needed(card)
    assert mana == 3
    paid_mana, _paid_life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            timing=CastManaTiming(cast_for_converted=True),
        ),
    )
    assert paid_mana == 3
    perm = place_on_battlefield(card, 0, fresh_game().zones)
    detail = apply_converted_on_etb(perm)
    assert detail is not None
    assert 'converted' in detail
    assert is_converted(perm)
