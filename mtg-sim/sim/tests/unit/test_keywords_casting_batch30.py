"""Unit tests for tiered, undaunted, and paradigm (batch 30)."""

from __future__ import annotations

from engine.abilities.keywords.casting.cast_mana import (
    AnnounceCastManaOptions,
    CastManaModifiers,
    resolve_announce_cast_mana,
)
from engine.abilities.keywords.casting.paradigm import (
    exile_for_paradigm,
    has_paradigm,
    is_paradigm_exiled_card,
    resolve_paradigm_upkeep,
)
from engine.abilities.keywords.casting.tiered import (
    has_tiered,
    normalize_tiered_mode,
    tiered_extra_mana,
    tiered_selection_error,
)
from engine.abilities.keywords.casting.undaunted import (
    has_undaunted,
    undaunted_reduction,
)
from engine.core.game_object import CardObject
from tests.conftest import fresh_game, make_instant


def test_tiered_requires_one_mode_and_adds_mana():
    """Tiered spells require exactly one mode and pay its additional cost."""
    card = make_instant(
        'Tier Spell',
        cmc=2,
        oracle=(
            'Tiered\n'
            'Choose one —\n'
            '• {1} — Draw a card.\n'
            '• {3} — Draw two cards.'
        ),
        mana_cost='{U}',
    )
    assert has_tiered(card)
    assert normalize_tiered_mode(card, 1) == 1
    assert tiered_extra_mana(card, 1) == 3
    assert tiered_selection_error(card, None) == "Tiered requires choosing exactly one mode"
    paid_mana, _life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(
            modifiers=CastManaModifiers(tiered_mode_index=1),
        ),
    )
    assert paid_mana == 4


def test_undaunted_reduces_cost_per_opponent():
    """Undaunted reduces generic mana by one per opponent."""
    card = make_instant(
        'Exhalation',
        cmc=7,
        oracle='Undaunted\nDestroy all creatures.',
        mana_cost='{5}{W}{W}',
    )
    game = fresh_game()
    assert has_undaunted(card)
    assert undaunted_reduction(game, card, 0) == 1
    paid_mana, _life = resolve_announce_cast_mana(
        card,
        AnnounceCastManaOptions(game=game, controller_idx=0),
    )
    assert paid_mana == 6


def test_paradigm_exiles_and_recasts_at_upkeep():
    """Paradigm exiles on resolve and logs a free cast each upkeep."""
    game = fresh_game()
    card_info = make_instant(
        'Dissertation',
        cmc=5,
        oracle='Paradigm\nTarget player draws two cards.',
        mana_cost='{3}{B}{B}',
    )
    assert has_paradigm(card_info)
    card = CardObject(controller_idx=0, owner_idx=0, card_info=card_info)
    exile_for_paradigm(game.zones, card, game)
    assert is_paradigm_exiled_card(card)
    assert card in game.zones.player_zones[0].exile
    assert 'Dissertation' in game.players[0].paradigm_spell_names
    details = resolve_paradigm_upkeep(game, 0)
    assert details == ['paradigm cast Dissertation']
