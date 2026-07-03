"""Tests for prepare_game_card_scripts_with_coverage API helper."""

from __future__ import annotations

from engine.cards.deck_script_store import (
    DeckMatchupScripts,
    prepare_game_card_scripts_with_coverage,
)
from tests.conftest import make_instant, make_land


def test_prepare_game_card_scripts_with_coverage(tmp_path, monkeypatch):
    """Matchup prep returns merged scripts and per-deck coverage."""
    monkeypatch.setenv('DECK_SCRIPT_CACHE_DIR', str(tmp_path))
    player = [make_instant('Lightning Bolt', oracle='Lightning Bolt deals 3 damage to any target.')]
    opponent = [make_land('Forest')]
    matchup = DeckMatchupScripts(
        player_deck_nid=99,
        player_cards=player,
        player_title='Player',
        meta_format='Modern',
        meta_archetype='Test',
        opponent_cards=opponent,
    )
    result = prepare_game_card_scripts_with_coverage(matchup)
    assert 'Lightning Bolt' in result.scripts
    assert result.player_coverage.scripted_unique_cards == 1
    assert result.opponent_coverage.by_source['skipped_land'] == 1
