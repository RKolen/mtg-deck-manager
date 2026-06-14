"""Unit tests for haunt, ingest, champion, and hideaway (batch 21)."""

from __future__ import annotations

from engine.abilities.keywords.other.champion import (
    apply_champion_etb,
    release_championed_creature,
)
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.haunt import apply_haunt_on_creature_death
from engine.abilities.keywords.other.hideaway import apply_hideaway_etb
from engine.abilities.keywords.other.ingest import apply_ingest_on_player_damage
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from tests.conftest import fresh_game, make_card, make_creature, make_instant, place_on_battlefield


def test_ingest_exiles_top_card():
    """Ingest exiles the top card of the damaged player's library."""
    game = fresh_game()
    top_card = make_instant('Top', oracle='Draw a card.')
    game.zones.player_zones[1].library.append(
        CardObject(controller_idx=1, owner_idx=1, card_info=top_card),
    )
    attacker = place_on_battlefield(
        make_creature('Eater', 2, 2, oracle='Ingest'),
        0,
        game.zones,
    )
    detail = apply_ingest_on_player_damage(game, attacker, 2, 1)
    assert detail is not None
    assert 'exiled' in detail
    assert len(game.zones.player_zones[1].library) == 0
    assert len(game.zones.player_zones[1].exile) == 1


def test_champion_exiles_host_on_etb():
    """Champion exiles another creature you control."""
    game = fresh_game()
    host = place_on_battlefield(make_creature('Host', 2, 2), 0, game.zones)
    champion = place_on_battlefield(
        make_creature('Hero', 3, 3, oracle='Champion'),
        0,
        game.zones,
    )
    detail = apply_champion_etb(game, champion)
    assert detail is not None
    assert host not in game.zones.battlefield
    assert len(game.zones.player_zones[0].exile) == 1


def test_champion_releases_creature_on_leave():
    """Champion returns the exiled creature when it leaves."""
    game = fresh_game()
    place_on_battlefield(make_creature('Host', 2, 2), 0, game.zones)
    champion = place_on_battlefield(
        make_creature('Hero', 3, 3, oracle='Champion'),
        0,
        game.zones,
    )
    apply_champion_etb(game, champion)
    game.zones.leave_battlefield(champion, Zone.GRAVEYARD, 'destroy', game)
    release_championed_creature(game, champion)
    assert any(perm.name == 'Host' for perm in game.zones.battlefield)


def test_hideaway_stashes_card_from_library():
    """Hideaway exiles cards from the top of the library."""
    game = fresh_game()
    hidden_card = make_instant('Hidden', oracle='Draw a card.')
    game.zones.player_zones[0].library.append(
        CardObject(controller_idx=0, owner_idx=0, card_info=hidden_card),
    )
    permanent = place_on_battlefield(
        make_card('Vault', type_line='Artifact', oracle='Hideaway 4'),
        0,
        game.zones,
    )
    detail = apply_hideaway_etb(game, permanent)
    assert detail is not None
    assert 'hideaway' in detail
    assert permanent.counters.get('hideaway_card_obj') is not None


def test_haunt_exiles_and_marks_target():
    """Haunt exiles the dying creature and haunts an opponent creature."""
    game = fresh_game()
    haunted = place_on_battlefield(make_creature('Victim', 2, 2), 1, game.zones)
    haunter = place_on_battlefield(
        make_creature('Spirit', 2, 2, oracle='Haunt'),
        0,
        game.zones,
    )
    game.zones.leave_battlefield(haunter, Zone.GRAVEYARD, 'destroy', game)
    detail = apply_haunt_on_creature_death(game, haunter)
    assert detail is not None
    assert haunted.counters.get('haunted') == 1


def test_champion_etb_hook_runs_from_registry():
    """Champion is wired through apply_etb_other_abilities."""
    game = fresh_game()
    place_on_battlefield(make_creature('Host', 2, 2), 0, game.zones)
    champion = place_on_battlefield(
        make_creature('Hero', 3, 3, oracle='Champion'),
        0,
        game.zones,
    )
    details = apply_etb_other_abilities(game, champion)
    assert any('champion' in line for line in details)
