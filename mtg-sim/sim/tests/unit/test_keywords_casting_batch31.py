"""Unit tests for web-slinging (batch 31)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaTiming,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.casting.web_slinging import (
    has_web_slinging,
    normalize_web_slinging_cast,
    return_creature_for_web_sling,
    web_sling_creature_error,
    web_slinging_mana_needed,
)
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_web_slinging_alternate_cost():
    """Web-slinging uses a lower alternate cost."""
    card = make_creature(
        'Web-Slinger',
        3,
        3,
        oracle='Web-slinging {1}{U}\nFlying',
        mana_cost='{3}{U}{U}',
    )
    assert has_web_slinging(card)
    assert normalize_web_slinging_cast(card, True)
    mana, _life = web_slinging_mana_needed(card)
    assert mana == 2
    paid_mana, _paid_life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            timing=CastManaTiming(cast_for_web_slinging=True),
        ),
    )
    assert paid_mana == 2


def test_web_slinging_returns_tapped_creature():
    """Web-slinging returns a tapped creature to hand."""
    game = fresh_game()
    assert web_sling_creature_error(game.zones, 0, None, paid=True) is not None
    perm = place_on_battlefield(make_creature('Acrobat', 2, 2), 0, game.zones)
    perm.tapped = True
    name = return_creature_for_web_sling(game.zones, 0, str(perm.obj_id))
    assert name == 'Acrobat'
    assert perm not in game.zones.battlefield
    assert perm in game.zones.player_zones[0].hand
