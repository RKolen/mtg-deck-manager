"""Unit tests for affinity (batch 35)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.other.affinity import has_affinity_for_artifacts
from tests.conftest import fresh_game, make_artifact, make_card, place_on_battlefield


def test_affinity_lowers_announce_cast_mana():
    """Affinity reduces mana paid when announcing a cast."""
    game = fresh_game()
    place_on_battlefield(make_artifact('Relic', oracle=''), 0, game.zones)
    card = make_card(
        'Myr Enforcer',
        mana_cost='{3}',
        oracle='Affinity for artifacts',
    )
    assert has_affinity_for_artifacts(card.oracle_text)
    paid_mana, _life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(zones=game.zones, controller_idx=0),
    )
    assert paid_mana == 2
