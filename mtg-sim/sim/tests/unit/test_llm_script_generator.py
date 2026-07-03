"""Tests for LLM card script generation fallback (Phase G)."""

from __future__ import annotations

import json

from engine.cards.deck_script_store import sync_deck_scripts
from engine.cards.effects import DealDamage, DrawCards
from engine.cards.llm_script_generator import (
    build_card_script_prompt,
    generate_card_script_json,
    llm_script_generation_enabled,
    validate_effect_json_list,
)
from tests.conftest import make_creature, make_instant


def test_llm_script_generation_disabled_by_default(monkeypatch):
    """LLM seeding is opt-in via LLM_SCRIPT_GENERATION."""
    monkeypatch.delenv('LLM_SCRIPT_GENERATION', raising=False)
    assert llm_script_generation_enabled() is False
    card = make_instant('Mystery', oracle='Draw two cards.')
    assert generate_card_script_json(card, generate_fn=lambda *_: '[]') is None


def test_llm_script_generation_enabled_with_env(monkeypatch):
    """LLM_SCRIPT_GENERATION=1 enables the generator gate."""
    monkeypatch.setenv('LLM_SCRIPT_GENERATION', '1')
    assert llm_script_generation_enabled() is True


def test_validate_effect_json_list_accepts_known_effects():
    """Valid effect JSON passes serde validation."""
    payload = [{'type': 'DrawCards', 'count': 2}]
    validated = validate_effect_json_list(payload)
    assert validated == payload


def test_validate_effect_json_list_rejects_unknown_type():
    """Unknown effect types are rejected."""
    payload = [{'type': 'CounterSpell', 'count': 1}]
    assert validate_effect_json_list(payload) is None


def test_generate_card_script_json_parses_fenced_response(monkeypatch):
    """Generator parses markdown-fenced JSON from the LLM."""
    monkeypatch.setenv('LLM_SCRIPT_GENERATION', '1')
    card = make_instant('Divination', oracle='Draw two cards.')

    def fake_generate(_prompt: str, _temp: float, _max_tokens: int) -> str:
        return '```json\n[{"type": "DrawCards", "count": 2}]\n```'

    result = generate_card_script_json(card, generate_fn=fake_generate)
    assert result is not None
    assert result[0]['type'] == 'DrawCards'


def test_generate_card_script_json_skips_creatures(monkeypatch):
    """Creature cards are not sent to the LLM."""
    monkeypatch.setenv('LLM_SCRIPT_GENERATION', '1')
    bear = make_creature('Bear')
    called = False

    def fake_generate(_prompt: str, _temp: float, _max_tokens: int) -> str:
        nonlocal called
        called = True
        return '[]'

    assert generate_card_script_json(bear, generate_fn=fake_generate) is None
    assert called is False


def test_build_card_script_prompt_includes_oracle():
    """Prompt embeds card metadata for the LLM."""
    card = make_instant('Shock', oracle='Shock deals 2 damage to any target.')
    prompt = build_card_script_prompt(card)
    assert 'Shock' in prompt
    assert 'deals 2 damage' in prompt
    assert 'DealDamage' in prompt


def test_sync_caches_llm_script_when_enabled(tmp_path, monkeypatch):
    """Deck sync writes LLM-generated scripts into the cache manifest."""
    monkeypatch.setenv('DECK_SCRIPT_CACHE_DIR', str(tmp_path))
    monkeypatch.setenv('LLM_SCRIPT_GENERATION', '1')
    card = make_instant(
        'Custom Draw',
        oracle='This spell is not inferrable by regex.',
    )

    def fake_llm(_card, **_kwargs):
        return [{'type': 'DrawCards', 'count': 3}]

    monkeypatch.setattr(
        'engine.cards.deck_script_store.generate_card_script_json',
        fake_llm,
    )

    scripts = sync_deck_scripts('nid:55', [card])
    assert 'Custom Draw' in scripts
    assert isinstance(scripts['Custom Draw'][0], DrawCards)
    assert scripts['Custom Draw'][0].count == 3

    manifest = json.loads((tmp_path / 'player' / '55.json').read_text(encoding='utf-8'))
    assert manifest['cards']['Custom Draw'][0]['type'] == 'DrawCards'


def test_sync_llm_damage_script_roundtrip(tmp_path, monkeypatch):
    """LLM DealDamage scripts deserialize and apply after cache sync."""
    monkeypatch.setenv('DECK_SCRIPT_CACHE_DIR', str(tmp_path))
    monkeypatch.setenv('LLM_SCRIPT_GENERATION', '1')
    card = make_instant('LLM Bolt', oracle='Deals 4 damage somehow.')

    def fake_llm(_card, **_kwargs):
        return [{'type': 'DealDamage', 'amount': 4, 'player_target': 'opponent'}]

    monkeypatch.setattr(
        'engine.cards.deck_script_store.generate_card_script_json',
        fake_llm,
    )
    scripts = sync_deck_scripts('nid:56', [card])
    assert isinstance(scripts['LLM Bolt'][0], DealDamage)
    assert scripts['LLM Bolt'][0].amount == 4
