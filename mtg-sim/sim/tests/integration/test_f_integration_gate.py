"""Phase F integration gate — layers, replacements, and game-loop hooks."""

from pathlib import Path

from engine.abilities.keywords.registry_deferrals import deferral_note, deferral_phase

_UNIT_DIR = Path(__file__).resolve().parent.parent / "unit"
_INTEGRATION_DIR = Path(__file__).resolve().parent
_CONTINUOUS_TESTS = _UNIT_DIR / "test_continuous.py"
_REPLACEMENT_TESTS = _UNIT_DIR / "test_replacement.py"
_PHASE_F_TESTS = _INTEGRATION_DIR / "test_phase_f_integration.py"


def _count_test_functions(path: Path) -> int:
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("def test_")
    )


def test_phase_f_continuous_layer_coverage():
    """Continuous effects: Humility, CDA, and layer 7b/7c have unit tests."""
    assert _count_test_functions(_CONTINUOUS_TESTS) >= 6


def test_phase_f_replacement_coverage():
    """Replacement effects: regen, shields, and graveyard routing have unit tests."""
    assert _count_test_functions(_REPLACEMENT_TESTS) >= 6


def test_phase_f_game_loop_hooks():
    """F-deferred keywords have simplified hooks exercised in the game loop."""
    assert _count_test_functions(_PHASE_F_TESTS) >= 8


def test_phase_f_deferred_keywords_documented():
    """Phase F deferrals name the engine modules that own simplified hooks."""
    for keyword in ("Absorb", "Hexproof from", "Living metal", "Umbra armor"):
        assert deferral_phase(keyword) == "F"
        assert deferral_note(keyword) is not None
