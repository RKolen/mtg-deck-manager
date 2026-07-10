"""Unit tests for scripted modal mode selection (Phase G)."""

from engine.cards.effects import DealDamage, DestroyPermanent, Modal
from engine.cards.modal_cast import (
    modal_selection_error,
    normalize_scripted_modal_mode,
    scripted_modal_mode_count,
)
from engine.cards.script_loader import scripted_effects_for
from tests.conftest import make_instant


def test_scripted_modal_mode_count_from_builtin():
    """Built-in Molten Collapse exposes two modal modes."""
    card = make_instant(
        "Molten Collapse",
        oracle="Choose one —\n• Destroy target creature.\n• Deals 3 damage.",
    )
    assert scripted_modal_mode_count(card) == 2


def test_normalize_scripted_modal_mode_rejects_out_of_range():
    """Invalid modal indices are rejected."""
    card = make_instant("Molten Collapse", oracle="Choose one —\n• A\n• B")
    assert normalize_scripted_modal_mode(card, 1) == 1
    assert normalize_scripted_modal_mode(card, 3) is None
    assert modal_selection_error(card, 3) == "Choose one: invalid mode index"


def test_scripted_modal_effects_resolve_selected_branch():
    """Modal mode index selects the matching effect type."""
    card = make_instant("Molten Collapse", oracle="Choose one")
    effects = scripted_effects_for(card)
    assert effects is not None
    modal = next(effect for effect in effects if isinstance(effect, Modal))
    assert isinstance(modal.modes[0], DestroyPermanent)
    assert isinstance(modal.modes[1], DealDamage)
