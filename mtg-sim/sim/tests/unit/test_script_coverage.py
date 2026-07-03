"""Tests for deck script coverage reporting (Phase G)."""

from __future__ import annotations

import json

from engine.cards.deck_script_store import seed_card_script, sync_deck_scripts_with_coverage
from engine.cards.script_coverage import build_coverage_report
from tests.conftest import make_creature, make_instant, make_land


def test_build_coverage_report_counts_spell_sources():
    """Coverage tracks scripted vs unscripted noncreature spells."""
    cards = [
        make_land('Forest'),
        make_creature('Bear'),
        make_instant('Shock', oracle='Shock deals 2 damage to any target.'),
        make_instant('Mystery', oracle='Do something weird.'),
    ]
    report = build_coverage_report(cards, {
        'Shock': 'builtin',
        'Mystery': 'unscripted',
    })
    assert report.total_unique_cards == 2
    assert report.scripted_unique_cards == 1
    assert report.scripted_pct == 0.5
    assert report.unscripted_spell_names == ('Mystery',)
    assert report.by_source['skipped_land'] == 1
    assert report.by_source['skipped_creature'] == 1


def test_seed_card_script_records_source():
    """Seeding reports builtin vs inferred vs unscripted sources."""
    shock = make_instant('Shock', oracle='Shock deals 2 damage to any target.')
    assert seed_card_script(shock, {}).source == 'builtin'

    unknown = make_instant('Mystery', oracle='Do something weird.')
    assert seed_card_script(unknown, {}).source == 'unscripted'

    bear = make_creature('Bear')
    assert seed_card_script(bear, {}).source == 'skipped_creature'


def test_sync_persists_card_sources_in_manifest(tmp_path, monkeypatch):
    """Sync writes per-card source metadata into the manifest JSON."""
    monkeypatch.setenv('DECK_SCRIPT_CACHE_DIR', str(tmp_path))
    deck = [
        make_instant('Lightning Bolt', oracle='Lightning Bolt deals 3 damage to any target.'),
        make_instant('Mystery', oracle='Do something weird.'),
    ]
    result = sync_deck_scripts_with_coverage('nid:12', deck, title='Test')
    assert result.coverage.scripted_unique_cards == 1
    assert 'Lightning Bolt' in result.scripts
    assert 'Mystery' not in result.scripts

    path = tmp_path / 'player' / '12.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    assert manifest['card_sources']['Lightning Bolt'] == 'builtin'
    assert manifest['card_sources']['Mystery'] == 'unscripted'
