"""Unit tests for echo, battle cry, flanking, partner, forecast, exhaust (batch 19)."""

from __future__ import annotations

from engine.abilities.keywords.other.battle_cry import apply_battle_cry_on_attack
from engine.abilities.keywords.other.echo import apply_echo_etb, resolve_echo_upkeep
from engine.abilities.keywords.other.exhaust import can_use_exhaust_ability, mark_exhaust_used
from engine.abilities.keywords.other.flanking import apply_flanking_on_block
from engine.abilities.keywords.other.forecast import can_forecast, has_forecast
from engine.abilities.keywords.other.partner import has_partner, validate_partner_deck
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from tests.conftest import fresh_game, make_creature, make_instant, place_on_battlefield


def test_echo_marks_creature_on_etb():
    """Echo creatures owe echo at the next upkeep."""
    game = fresh_game()
    echoer = place_on_battlefield(
        make_creature('Shivan', 5, 4, oracle='Echo {2}{R}{R}'),
        0,
        game.zones,
    )
    detail = apply_echo_etb(echoer)
    assert detail is not None
    assert echoer.counters.get('echo') == 1


def test_echo_upkeep_sacrifices_without_mana():
    """Echo sacrifices when echo cost cannot be paid."""
    game = fresh_game()
    echoer = place_on_battlefield(
        make_creature('Shivan', 5, 4, oracle='Echo {2}{R}{R}'),
        0,
        game.zones,
    )
    apply_echo_etb(echoer)
    details = resolve_echo_upkeep(game, 0, lambda _p, _m: False)
    assert any('sacrificed' in line for line in details)
    assert echoer not in game.zones.battlefield


def test_battle_cry_buffs_other_attackers():
    """Battle cry gives +1/+0 to other attacking creatures."""
    game = fresh_game()
    leader = place_on_battlefield(
        make_creature('Leader', 2, 2, oracle='Battle cry'),
        0,
        game.zones,
        sick=False,
    )
    ally = place_on_battlefield(make_creature('Ally', 1, 1), 0, game.zones, sick=False)
    detail = apply_battle_cry_on_attack(
        game,
        leader,
        [str(leader.obj_id), str(ally.obj_id)],
    )
    assert detail is not None
    assert ally.counters.get('battle_cry', 0) == 1


def test_flanking_weakens_blocker():
    """Flanking gives blocking creatures without flanking -1/-1."""
    game = fresh_game()
    attacker = place_on_battlefield(
        make_creature('Knight', 2, 2, oracle='Flanking'),
        0,
        game.zones,
        sick=False,
    )
    blocker = place_on_battlefield(make_creature('Blocker', 2, 2), 1, game.zones)
    detail = apply_flanking_on_block(attacker, blocker)
    assert detail is not None
    assert blocker.counters.get('-1/-1', 0) == 1


def test_partner_deck_validation():
    """Partner decks must include two partner creatures."""
    solo = make_creature('Akiri', 3, 3, oracle='Partner')
    assert has_partner(solo)
    assert validate_partner_deck([solo]) is not None
    partner = make_creature('Thrasios', 1, 4, oracle='Partner with Akiri')
    assert validate_partner_deck([solo, partner]) is None


def test_forecast_available_on_draw_step():
    """Forecast can be used during the simplified draw step."""
    card = make_instant('Gelid', oracle='Forecast — Draw a card.')
    assert has_forecast(card)
    assert can_forecast(card, 'draw', True)
    assert not can_forecast(card, 'main1', True)


def test_exhaust_marks_used():
    """Exhaust abilities can only be used once."""
    perm = place_on_battlefield(
        make_creature('Worker', 2, 2, oracle='Exhaust — Draw a card.'),
        0,
        fresh_game().zones,
    )
    assert can_use_exhaust_ability(perm)
    mark_exhaust_used(perm)
    assert not can_use_exhaust_ability(perm)


def test_echo_etb_hook_runs_from_registry():
    """Echo is wired through apply_etb_other_abilities."""
    game = fresh_game()
    echoer = place_on_battlefield(
        make_creature('Shivan', 5, 4, oracle='Echo {2}{R}'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, echoer)
    assert any('echo' in line for line in details)
