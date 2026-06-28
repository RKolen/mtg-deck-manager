"""Unit tests for casting batch 38: aftermath, assist, bargain, bestow, spectacle, escape."""

from __future__ import annotations

from engine.abilities.keywords.casting.aftermath import (
    can_cast_aftermath,
    has_aftermath_card,
)
from engine.abilities.keywords.casting.assist import has_assist_card, resolve_assist_for_cast
from engine.abilities.keywords.casting.bargain import (
    bargain_draw_on_cast,
    has_bargain_card,
    normalize_paid_bargain,
)
from engine.abilities.keywords.casting.bestow import (
    bestow_host_error,
    bestow_mana_needed,
    has_bestow_card,
    normalize_bestow,
)
from engine.abilities.keywords.casting.escape import (
    escape_exiles_required,
    escape_payment_error,
    has_escape_card,
)
from engine.abilities.keywords.casting.spectacle import (
    has_spectacle_card,
    normalize_spectacle_cast,
    spectacle_available,
)
from engine.core.game_object import CardObject
from tests.conftest import (
    _CardStats,
    fresh_game,
    make_card,
    make_creature,
    make_instant,
    place_on_battlefield,
)


def test_aftermath_keyword_casts_from_graveyard_in_main():
    """Aftermath card detection and main-phase graveyard timing."""
    card = make_card(
        'Start',
        type_line='Sorcery — Adventure',
        oracle='Aftermath\nDraw two cards.',
        stats=_CardStats(cmc=2.0),
    )
    assert has_aftermath_card(card)
    assert can_cast_aftermath(card, 'main1', True)
    assert not can_cast_aftermath(card, 'attack', True)


def test_assist_keyword_reduces_announced_mana():
    """Assist card detection and mana contribution from allies."""
    card = make_instant('Rally', cmc=5, oracle='Assist\nDraw two cards.')
    assert has_assist_card(card)
    remaining, applied, err = resolve_assist_for_cast(card, 5, 3)
    assert err is None
    assert remaining == 2
    assert applied == 3


def test_bargain_keyword_triggers_draw_when_paid():
    """Bargain card detection and draw effect when bargain is paid."""
    spell = make_instant('Deal', oracle='Bargain\nDraw a card.')
    assert has_bargain_card(spell)
    assert normalize_paid_bargain(spell, True)
    assert bargain_draw_on_cast(spell, True)


def test_bestow_keyword_targets_friendly_creature():
    """Bestow card detection, cost parsing, and host validation."""
    game = fresh_game()
    host = place_on_battlefield(make_creature('Host', 2, 2), 0, game.zones)
    card = make_creature('Spirit', 2, 2, oracle='Bestow {3}{W}\nFlying')
    assert has_bestow_card(card)
    assert bestow_mana_needed(card) == (4, 0)
    assert normalize_bestow(card, str(host.obj_id))
    assert bestow_host_error(game.zones, 0, str(host.obj_id)) is None


def test_spectacle_keyword_available_after_opponent_loses_life():
    """Spectacle card detection and availability after opponent damage."""
    game = fresh_game()
    game.players[1].was_dealt_damage_this_turn = True
    card = make_instant('Spectacle', oracle='Spectacle {R}\nDeal 2 damage.')
    assert has_spectacle_card(card)
    assert spectacle_available(game, 0)
    assert normalize_spectacle_cast(card, True, available=True)


def test_escape_keyword_requires_graveyard_exiles():
    """Escape card detection and graveyard exile payment validation."""
    game = fresh_game()
    card = make_instant(
        'Uro',
        oracle='Escape—{G}{G}, Exile five other cards from your graveyard.',
    )
    assert has_escape_card(card)
    assert escape_exiles_required(card) == 5
    graveyard = game.zones.player_zones[0].graveyard
    graveyard.append(CardObject(controller_idx=0, owner_idx=0, card_info=card))
    payment_err = escape_payment_error(game.zones, 0, 0, [1, 2], card)
    assert payment_err is not None
