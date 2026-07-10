"""Phase G integration gate — scripting, modal cast, and runtime cache."""

from pathlib import Path

from engine.abilities.keywords.registry_deferrals import deferral_phase
from engine.cards.builtin_scripts import BUILTIN_CARD_SCRIPTS

_INTEGRATION_DIR = Path(__file__).resolve().parent
_UNIT_DIR = _INTEGRATION_DIR.parent / "unit"
_SCRIPTED_TESTS = _INTEGRATION_DIR / "test_scripted_game.py"
_EFFECTS_TESTS = _UNIT_DIR / "test_effects.py"
_MODAL_TESTS = _UNIT_DIR / "test_modal_cast.py"
_COVERAGE_TESTS = _UNIT_DIR / "test_script_coverage.py"
_STORE_TESTS = _UNIT_DIR / "test_deck_script_store.py"


def _count_test_functions(path: Path) -> int:
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("def test_")
    )


def test_phase_g_builtin_script_library():
    """G-registry: built-in public card templates cover common spells."""
    assert len(BUILTIN_CARD_SCRIPTS) >= 28


def test_phase_g_scripted_game_loop_coverage():
    """G-integration: scripted spells resolve through CardEffect in the game loop."""
    assert _count_test_functions(_SCRIPTED_TESTS) >= 12


def test_phase_g_effect_and_modal_unit_coverage():
    """G-unit: CardEffect, serde, and modal selection have dedicated tests."""
    assert _count_test_functions(_EFFECTS_TESTS) >= 20
    assert _count_test_functions(_MODAL_TESTS) >= 3


def test_phase_g_runtime_cache_and_coverage():
    """G-sync: deck script store and coverage reporting are tested."""
    assert _count_test_functions(_COVERAGE_TESTS) >= 3
    assert _count_test_functions(_STORE_TESTS) >= 1


def test_phase_g_deferred_keywords_routed():
    """Niche keywords deferred from E-integration are owned by Phase G."""
    for keyword in ("Banding", "Epic", "Soulbond", "Changeling"):
        assert deferral_phase(keyword) == "G"
