"""Unit tests for surge (batch 24)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaTiming,
    _OpponentDamageCasts,
    _TimingAvailability,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.casting.surge import (
    has_surge,
    normalize_surge_cast,
    surge_available,
    surge_mana_needed,
)
from tests.conftest import fresh_game, make_instant

_SURGE_ORACLE = (
    'Surge {R} (You may cast this spell for its surge cost if you or a teammate '
    'has dealt damage to an opponent this turn.)\n'
    'Deal 2 damage to any target.'
)


def test_surge_alternate_cost_when_opponent_was_damaged():
    """Surge uses the lower alternate cost when available."""
    game = fresh_game()
    game.players[1].was_dealt_damage_this_turn = True
    card = make_instant('Bolt', cmc=3, oracle=_SURGE_ORACLE, mana_cost='{2}{R}')
    assert has_surge(card)
    assert surge_available(game, 0)
    assert normalize_surge_cast(card, True, available=True)
    mana, _life = surge_mana_needed(card)
    assert mana == 1
    paid_mana, _paid_life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            timing=CastManaTiming(
                opponent_damage=_OpponentDamageCasts(surge=True),
                available=_TimingAvailability(surge_available=True),
            ),
        ),
    )
    assert paid_mana == 1


def test_surge_unavailable_without_damage():
    """Surge cannot be used when no opponent was dealt damage."""
    game = fresh_game()
    card = make_instant('Strike', cmc=2, oracle=_SURGE_ORACLE)
    assert not surge_available(game, 0)
    assert not normalize_surge_cast(card, True, available=False)
