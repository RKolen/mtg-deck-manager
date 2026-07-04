"""Unit tests for keyword registry deferrals and routing (Phase E)."""

from engine.abilities.keywords.registry import integration_routing_counts
from engine.abilities.keywords.registry_deferrals import (
    deferral_phase,
    entries_routed_to_casting,
    implementation_route,
    is_phase_g_deferred,
)


def test_casting_routed_includes_evoke_catalog_mismatch():
    """Evoke is cataloged as ability_other but implemented under casting/."""
    routed = entries_routed_to_casting()
    assert 'Evoke' in routed
    assert implementation_route('Evoke') == 'casting/'


def test_scavenge_routes_to_activated():
    """Scavenge is implemented via the activated API."""
    assert implementation_route('Scavenge') == 'activated/'


def test_banding_deferred_to_phase_g():
    """Banding is explicitly deferred to Phase G scripting."""
    assert is_phase_g_deferred('Banding')
    assert deferral_phase('Banding') == 'G'


def test_integration_routing_counts_nonzero():
    """Routing summary exposes casting/activated mismatches and deferrals."""
    counts = integration_routing_counts()
    assert counts['casting_routed'] >= 30
    assert counts['phase_g_deferred'] >= 10
