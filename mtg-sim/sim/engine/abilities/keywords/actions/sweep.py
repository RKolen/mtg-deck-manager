"""Sweep ability word on spells: return lands to hand."""

from __future__ import annotations

from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import CardObject
from engine.core.zones import ZoneManager


def apply_sweep(zones: ZoneManager, controller_idx: int, oracle_text: str) -> str | None:
    """Return all lands you control to your hand when Sweep is on the spell."""
    if not has_registered_keyword(oracle_text, 'Sweep'):
        return None
    if 'land' not in oracle_text.lower():
        return None
    lands = [
        perm
        for perm in list(zones.battlefield)
        if perm.controller_idx == controller_idx and 'Land' in perm.type_line
    ]
    returned = 0
    for perm in lands:
        if not isinstance(perm.source, CardObject):
            continue
        zones.battlefield.remove(perm)
        zones.player_zones[controller_idx].hand.append(perm.source)
        returned += 1
    if returned == 0:
        return None
    return f"sweep returned {returned} land(s)"
