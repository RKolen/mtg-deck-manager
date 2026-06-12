"""Unit tests for escalate and bargain (batch 19)."""

from __future__ import annotations

from engine.abilities.keywords.casting.bargain import (
    bargain_sacrifice_error,
    has_bargain,
    normalize_paid_bargain,
)
from engine.abilities.keywords.casting.escalate import escalate_extra_mana, has_escalate
from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaTiming,
    _TimingAvailability,
    resolve_announce_cast_mana,
)
from tests.conftest import (
    fresh_game,
    make_artifact,
    make_creature,
    make_instant,
    place_on_battlefield,
)

_ESCALATE_ORACLE = (
    'Escalate {1}{U} (Pay this cost for each target beyond the first.)\n'
    'Counter target spell.'
)
_BARGAIN_ORACLE = (
    'Bargain (You may sacrifice an artifact as an additional cost to cast this spell. '
    'If you do, draw a card.)\n'
    'Draw a card.'
)


def test_has_escalate_and_extra_mana():
    """Escalate adds mana for each extra target."""
    card = make_instant('Counter', cmc=2, mana_cost='{U}{U}', oracle=_ESCALATE_ORACLE)
    assert has_escalate(card)
    assert escalate_extra_mana(card, 2) == 4


def test_announce_cast_mana_includes_escalate():
    """Escalate payments are included in announce mana."""
    card = make_instant('Counter', cmc=2, mana_cost='{U}{U}', oracle=_ESCALATE_ORACLE)
    mana, _life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            timing=CastManaTiming(
                available=_TimingAvailability(escalate_extra_targets=1),
            ),
        ),
    )
    assert mana == 4


def test_bargain_requires_artifact_sacrifice():
    """Bargain validates an artifact sacrifice."""
    game = fresh_game()
    spell = make_instant('Deal', cmc=2, oracle=_BARGAIN_ORACLE)
    creature = place_on_battlefield(make_creature('Guy', 1, 1), 0, game.zones)
    assert has_bargain(spell)
    assert normalize_paid_bargain(spell, True)
    err = bargain_sacrifice_error(
        game.zones,
        0,
        spell,
        True,
        [creature.obj_id],
    )
    assert err is not None


def test_bargain_accepts_artifact():
    """Bargain accepts sacrificing an artifact you control."""
    game = fresh_game()
    spell = make_instant('Deal', cmc=2, oracle=_BARGAIN_ORACLE)
    token = place_on_battlefield(make_artifact('Clue'), 0, game.zones)
    err = bargain_sacrifice_error(game.zones, 0, spell, True, [token.obj_id])
    assert err is None
