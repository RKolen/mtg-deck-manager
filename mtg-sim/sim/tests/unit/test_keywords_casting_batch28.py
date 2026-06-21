"""Unit tests for squad (batch 28)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaModifiers,
    _RepeatCastCounts,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.casting.squad import (
    apply_squad_on_etb,
    has_squad,
    normalize_squad_times,
    squad_extra_mana,
)
from tests.conftest import fresh_game, make_creature, place_on_battlefield


def test_squad_adds_extra_mana_and_tokens():
    """Squad pays {X} and creates X tokens on ETB."""
    card = make_creature(
        'Recruit',
        2,
        2,
        oracle='Squad {2} (As an additional cost to cast this spell, pay {2} any number of times.)',
    )
    assert has_squad(card)
    assert normalize_squad_times(card, 2) == 2
    assert squad_extra_mana(card, 2) == 2
    paid_mana, _paid_life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            modifiers=CastManaModifiers(repeat=_RepeatCastCounts(squad_times=2)),
        ),
    )
    assert paid_mana == 4
    game = fresh_game()
    perm = place_on_battlefield(card, 0, game.zones)
    detail = apply_squad_on_etb(game.zones, perm, 2)
    assert detail is not None
    assert '2 token' in detail
    tokens = [
        p for p in game.zones.battlefield
        if p.is_token and 'Recruit Token' in p.name
    ]
    assert len(tokens) == 2
