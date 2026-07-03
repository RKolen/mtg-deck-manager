"""Tests for oracle-to-effect inference (Phase G)."""

from __future__ import annotations

from engine.cards.deck_script_store import sync_deck_scripts
from engine.cards.effects import (
    DealDamage,
    DestroyPermanent,
    DiscardCards,
    DrawCards,
    Modal,
    Scry,
    Surveil,
)
from engine.cards.oracle_infer import infer_effects_from_oracle
from tests.conftest import make_creature, make_instant


def test_infer_shock_deal_damage():
    """Burn spells infer DealDamage from oracle text."""
    shock = make_instant('Shock', oracle='Shock deals 2 damage to any target.')
    effects = infer_effects_from_oracle(shock) or ()
    assert len(effects) >= 1
    first = effects[0]
    assert isinstance(first, DealDamage)
    assert first.amount == 2


def test_infer_opt_draws_one():
    """Draw spells infer DrawCards and Scry from oracle text."""
    opt = make_instant('Opt', oracle='Scry 1.\nDraw a card.')
    effects = infer_effects_from_oracle(opt) or ()
    assert any(isinstance(effect, DrawCards) for effect in effects)
    assert any(isinstance(effect, Scry) for effect in effects)


def test_infer_creature_returns_none():
    """Creature cards are not inferred as one-shot spell scripts."""
    bear = make_creature('Grizzly Bears')
    assert infer_effects_from_oracle(bear) is None


def test_sync_infers_oracle_when_no_builtin(tmp_path, monkeypatch):
    """Deck sync writes inferred scripts for cards without built-in templates."""
    monkeypatch.setenv('DECK_SCRIPT_CACHE_DIR', str(tmp_path))
    deck = [make_instant('Shock', oracle='Shock deals 2 damage to any target.')]
    scripts = sync_deck_scripts('nid:7', deck)
    assert 'Shock' in scripts
    assert isinstance(scripts['Shock'][0], DealDamage)


def test_infer_surveil_and_discard():
    """Supplemental oracle keywords infer Surveil and DiscardCards."""
    surveil = make_instant('Test', oracle='Surveil 2.')
    effects = infer_effects_from_oracle(surveil) or ()
    assert any(isinstance(effect, Surveil) for effect in effects)

    seize = make_instant(
        'Thoughtseize',
        oracle='Target player discards a card.',
    )
    effects = infer_effects_from_oracle(seize) or ()
    assert any(isinstance(effect, DiscardCards) for effect in effects)


def test_infer_modal_spell():
    """Choose-one charms infer a Modal effect with per-clause modes."""
    collapse = make_instant(
        'Molten Collapse',
        oracle=(
            'Choose one —\n'
            '• Destroy target creature or planeswalker.\n'
            '• Molten Collapse deals 3 damage to any target.'
        ),
    )
    effects = infer_effects_from_oracle(collapse) or ()
    modal = next(effect for effect in effects if isinstance(effect, Modal))
    assert isinstance(modal.modes[0], DestroyPermanent)
    assert isinstance(modal.modes[1], DealDamage)
    assert modal.modes[1].amount == 3


def test_infer_scry_and_draw_together():
    """Compound spells infer Scry and DrawCards from oracle text."""
    serum = make_instant('Serum Visions', oracle='Scry 2, then draw a card.')
    effects = infer_effects_from_oracle(serum) or ()
    assert any(isinstance(effect, DrawCards) for effect in effects)
    assert any(isinstance(effect, Scry) for effect in effects)


def test_opt_serde_roundtrip_via_sync(tmp_path, monkeypatch):
    """Inferred Scry effects persist through deck cache JSON."""
    monkeypatch.setenv('DECK_SCRIPT_CACHE_DIR', str(tmp_path))
    deck = [make_instant('Opt', oracle='Scry 1.\nDraw a card.')]
    scripts = sync_deck_scripts('nid:8', deck)
    assert 'Opt' in scripts
    assert any(isinstance(effect, Scry) for effect in scripts['Opt'])
