"""Phase E integration gate — minimum bar before Phase G scripting expands."""

from pathlib import Path

import pytest

from engine.abilities.keywords.registry_deferrals import deferral_phase
from engine.abilities.keywords.other.etb_handlers import etb_detail_producer_count
from engine.abilities.keywords.registry import integration_routing_counts, registry_summary

_INTEGRATION_DIR = Path(__file__).resolve().parent
_ABILITY_OTHER_TESTS = _INTEGRATION_DIR / "test_keywords_game_ability_other.py"
_COMBAT_OTHER_TESTS = _INTEGRATION_DIR / "test_keywords_game_combat_other.py"
_CASTING_TESTS = _INTEGRATION_DIR / "test_keywords_game.py"


def _count_test_functions(path: Path) -> int:
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("def test_")
    )


def test_phase_e_registry_complete():
    """E-registry: all Scryfall keywords are cataloged."""
    summary = registry_summary()
    assert summary["total"] >= 359


def test_phase_e_integration_routing_documented():
    """Explicit deferrals route niche keywords to Phase G/F."""
    counts = integration_routing_counts()
    assert counts["casting_routed"] >= 30
    assert counts["activated_routed"] >= 10
    assert counts["phase_g_deferred"] >= 10
    assert counts["phase_f_deferred"] >= 3


def test_phase_e_integration_game_loop_coverage():
    """E-integration: deck-relevant keywords have game-loop tests."""
    ability_other = _count_test_functions(_ABILITY_OTHER_TESTS)
    combat_other = _count_test_functions(_COMBAT_OTHER_TESTS)
    casting = _count_test_functions(_CASTING_TESTS)
    assert ability_other >= 40
    assert combat_other >= 8
    assert casting >= 30
    assert etb_detail_producer_count() >= 37


@pytest.mark.parametrize(
    "keyword,phase",
    [
        ("Banding", "G"),
        ("Epic", "G"),
        ("Absorb", "F"),
        ("Umbra armor", "F"),
    ],
)
def test_phase_e_deferred_keywords_routed(keyword: str, phase: str):
    """Deferred keywords are explicitly owned by Phase G or F."""
    assert deferral_phase(keyword) == phase
