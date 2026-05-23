"""Unit tests for ability_other keywords (Living weapon, Affinity)."""

from __future__ import annotations

from engine.abilities.keywords.other.affinity import (
    affinity_reduction,
    has_affinity_for_artifacts,
)
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.cards.oracle_parse import is_affordable, mana_needed_to_cast
from tests.conftest import fresh_game, make_artifact, make_card, place_on_battlefield

_LIVING_WEAPON_ORACLE = (
    'Living weapon (When this Equipment enters, create a 0/0 black Germ '
    'creature token, then attach this to it.)'
)
_AFFINITY_ORACLE = (
    'Affinity for artifacts (This spell costs {1} less to cast for each '
    'artifact you control.)'
)


def test_living_weapon_creates_germ_and_attaches():
    """Living weapon ETB creates a Germ token attached to the equipment."""
    game = fresh_game()
    sword = place_on_battlefield(
        make_card(
            'Batterskull',
            type_line='Artifact — Equipment',
            oracle=_LIVING_WEAPON_ORACLE,
        ),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game.zones, sword)
    assert details
    assert sword.attached_to is not None
    host = game.zones.find_permanent(sword.attached_to)
    assert host is not None
    assert 'Germ' in host.type_line


def test_affinity_reduces_cast_cost():
    """Affinity for artifacts lowers mana needed to cast."""
    game = fresh_game()
    for _ in range(2):
        place_on_battlefield(make_artifact('Vault', oracle=''), 0, game.zones)
    card = make_card(
        'Frogmite',
        cmc=4.0,
        mana_cost='{4}',
        oracle=_AFFINITY_ORACLE,
    )
    assert has_affinity_for_artifacts(card.oracle_text)
    assert affinity_reduction(card, game.zones, 0) == 2
    assert mana_needed_to_cast(card, game.zones, 0) == 2
    assert is_affordable(card, 2, game.zones, 0)
    assert not is_affordable(card, 1, game.zones, 0)
