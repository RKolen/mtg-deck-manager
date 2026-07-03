"""Tests for runtime deck script cache sync (Phase G)."""

from __future__ import annotations

import json

from deck_registry import CardInfo
from engine.cards.builtin_scripts import BUILTIN_CARD_SCRIPTS
from engine.cards.deck_script_store import (
    DeckMatchupScripts,
    deck_fingerprint,
    prepare_game_card_scripts,
    sync_deck_scripts,
)
from engine.cards.script_loader import has_script, scripted_card_names
from engine.core.game_state import GameState
from engine.core.turn_structure import TurnRunner
from engine.core.zones import ZoneManager
from engine.rules.stack import Stack
from tests.conftest import make_instant, make_land


def _instant(name: str, oracle: str = '') -> CardInfo:
    return make_instant(name, oracle=oracle or name)


def test_deck_fingerprint_changes_when_deck_changes():
    """Fingerprint invalidates cache when deck composition changes."""
    deck_a = [_instant('Lightning Bolt'), make_land('Forest')]
    deck_b = [_instant('Lightning Bolt'), _instant('Lightning Bolt')]
    assert deck_fingerprint(deck_a) != deck_fingerprint(deck_b)


def test_sync_deck_scripts_seeds_from_builtins(tmp_path, monkeypatch):
    """First sync writes JSON and seeds known cards from built-in templates."""
    monkeypatch.setenv('DECK_SCRIPT_CACHE_DIR', str(tmp_path))
    deck = [_instant('Lightning Bolt'), _instant('Unknown Card', 'Do nothing.')]
    scripts = sync_deck_scripts('nid:42', deck, title='Test Deck')

    assert 'Lightning Bolt' in scripts
    assert 'Unknown Card' not in scripts
    path = tmp_path / 'player' / '42.json'
    assert path.exists()
    manifest = json.loads(path.read_text(encoding='utf-8'))
    assert manifest['fingerprint'] == deck_fingerprint(deck)
    assert manifest['title'] == 'Test Deck'
    assert 'Lightning Bolt' in manifest['cards']


def test_sync_deck_scripts_preserves_existing_entries_on_refresh(tmp_path, monkeypatch):
    """When deck changes, previously cached per-card scripts are kept."""
    monkeypatch.setenv('DECK_SCRIPT_CACHE_DIR', str(tmp_path))
    deck_v1 = [_instant('Lightning Bolt')]
    sync_deck_scripts('nid:99', deck_v1)

    path = tmp_path / 'player' / '99.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['cards']['Custom Spell'] = [{'type': 'draw', 'count': 2}]
    path.write_text(json.dumps(manifest), encoding='utf-8')

    deck_v2 = [_instant('Lightning Bolt'), _instant('Custom Spell', 'Draw two cards.')]
    scripts = sync_deck_scripts('nid:99', deck_v2)
    assert 'Custom Spell' in scripts
    assert scripts['Custom Spell'][0].__class__.__name__ == 'DrawCards'


def test_prepare_game_card_scripts_merges_player_and_meta(tmp_path, monkeypatch):
    """Player deck scripts override meta scripts for the same card name."""
    monkeypatch.setenv('DECK_SCRIPT_CACHE_DIR', str(tmp_path))
    player = [_instant('Lightning Bolt')]
    opponent = [_instant('Doom Blade')]
    merged = prepare_game_card_scripts(
        DeckMatchupScripts(
            player_deck_nid=1,
            player_cards=player,
            player_title='Player',
            meta_format='Modern',
            meta_archetype='Jund',
            opponent_cards=opponent,
        ),
    )
    assert 'Lightning Bolt' in merged
    assert 'Doom Blade' in merged
    assert tmp_path / 'player' / '1.json'
    assert (tmp_path / 'meta' / 'modern' / 'jund.json').exists()


def test_script_loader_uses_game_scripts_over_builtin_fallback():
    """Per-game scripts drive resolution; builtins apply when game has none."""
    bolt = _instant('Lightning Bolt')
    assert has_script(bolt) is True
    assert bolt.name in scripted_card_names()

    state = GameState(
        game_id='test',
        zones=ZoneManager(),
        players=[],
        turn=TurnRunner(),
        stack=Stack(),
    )
    state.card_scripts = {'Only In Deck': BUILTIN_CARD_SCRIPTS['Lightning Bolt']}
    assert has_script(bolt, state) is False
    assert has_script(_instant('Only In Deck'), state) is True
    assert scripted_card_names(state) == frozenset({'Only In Deck'})
