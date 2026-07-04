"""Explicit Phase E integration deferrals and catalog routing notes.

Scryfall catalogs some cast/activated mechanics under ``ability_other`` while
implementation lives under ``casting/`` or ``activated/``. Other niche keywords
are intentionally deferred to Phase G (CardEffect scripts) or Phase F (layers).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from engine.abilities.keywords.registry_data import KEYWORD_ENTRIES

DeferralPhase = Literal['G', 'F']
_KEYWORDS_ROOT = Path(__file__).resolve().parent

# Niche mechanics: detected in the registry; owned-deck fidelity via Phase G scripts.
_PHASE_G_DEFERRED: frozenset[str] = frozenset({
    'Banding',
    'Soulbond',
    'Doctor\'s companion',
    'Friends forever',
    'Choose a background',
    'Hidden agenda',
    'Double agenda',
    'Changeling',
    'Epic',
    'Phasing',
    'Cumulative upkeep',
    'Firebending',
})

# Layer / replacement depth deferred to Phase F beyond simplified hooks.
_PHASE_F_DEFERRED: frozenset[str] = frozenset({
    'Absorb',
    'Hexproof from',
    'Living metal',
    'Umbra armor',
})

_PHASE_G_NOTES: dict[str, str] = {
    'Banding': 'Combat damage assignment; use CardEffect for banded attacks',
    'Soulbond': 'Two-card pairing state; script per card',
    'Epic': 'Upkeep free-cast simplified; script exact epic spells',
    'Phasing': 'Phased-out layers; full CR in Phase F/G',
    'Changeling': 'Type-changing; script when card-specific types matter',
}

_ACTIVATED_INLINE: frozenset[str] = frozenset({
    'Scavenge',
    'Cycling',
    'Basic landcycling',
    'Landcycling',
    'Plainscycling',
    'Islandcycling',
    'Swampcycling',
    'Mountaincycling',
    'Forestcycling',
    'Slivercycling',
    'Typecycling',
    'Wizardcycling',
})


def _keyword_stem(name: str) -> str:
    return (
        name.lower()
        .replace(' ', '_')
        .replace('-', '_')
        .replace("'", '')
    )


@lru_cache(maxsize=1)
def entries_routed_to_casting() -> frozenset[str]:
    """Keywords cataloged outside ``casting`` but implemented under ``casting/``."""
    casting_dir = _KEYWORDS_ROOT / 'casting'
    routed: set[str] = set()
    for name, kind, category in KEYWORD_ENTRIES:
        if kind != 'ability' or category == 'casting':
            continue
        if (casting_dir / f'{_keyword_stem(name)}.py').is_file():
            routed.add(name)
    return frozenset(routed)


@lru_cache(maxsize=1)
def entries_routed_to_activated() -> frozenset[str]:
    """Keywords cataloged outside ``activated`` but implemented via activated API."""
    activated_dir = _KEYWORDS_ROOT / 'activated'
    routed: set[str] = set(_ACTIVATED_INLINE)
    for name, kind, category in KEYWORD_ENTRIES:
        if kind != 'ability' or category == 'activated':
            continue
        if (activated_dir / f'{_keyword_stem(name)}.py').is_file():
            routed.add(name)
    return frozenset(routed)


def deferral_phase(keyword: str) -> DeferralPhase | None:
    """Return G/F when a keyword is explicitly deferred; else None."""
    canonical = keyword.strip()
    if canonical in _PHASE_G_DEFERRED:
        return 'G'
    if canonical in _PHASE_F_DEFERRED:
        return 'F'
    return None


def is_phase_g_deferred(keyword: str) -> bool:
    """Return True when scripting (Phase G) owns full fidelity for this keyword."""
    return deferral_phase(keyword) == 'G'


def deferral_note(keyword: str) -> str | None:
    """Return a short deferral rationale when one exists."""
    return _PHASE_G_NOTES.get(keyword)


def implementation_route(keyword: str) -> str | None:
    """Return engine package route when catalog category differs from code layout."""
    if keyword in entries_routed_to_casting():
        return 'casting/'
    if keyword in entries_routed_to_activated():
        return 'activated/'
    phase = deferral_phase(keyword)
    if phase == 'G':
        return 'phase_g_script'
    if phase == 'F':
        return 'phase_f_layers'
    return None
