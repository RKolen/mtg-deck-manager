"""Warp: alternate cost; permanent is exiled at end of turn (simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost
from engine.core.zones import Zone, ZoneManager

_WARP_RE = re.compile(
    r'warp\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_WARP_EXILE = 'warp_exile'


def has_warp(card: CardInfo) -> bool:
    """Return True when the card has warp."""
    return has_registered_keyword(card.oracle_text, 'Warp') or bool(
        _WARP_RE.search(card.oracle_text or '')
    )


def warp_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the warp cost."""
    match = _WARP_RE.search(card.oracle_text or '')
    if match is None:
        return alt_cost_mana_needed(None, card)
    cost = ManaCost.parse(match.group(1))
    return alt_cost_mana_needed(cost, card)


def normalize_warp_cast(card: CardInfo, cast_for_warp: bool) -> bool:
    """Return whether this cast uses the warp cost."""
    return cast_for_warp and has_warp(card)


def apply_warp_on_resolve(permanent: Permanent) -> str | None:
    """Mark a permanent cast for warp to exile at end of turn."""
    permanent.counters[_WARP_EXILE] = 1
    return f"warp {permanent.name} (exile at end of turn)"


def exile_warp_permanents(zones: ZoneManager, player_idx: int) -> list[str]:
    """Exile permanents marked by warp at end of turn."""
    details: list[str] = []
    for perm in list(zones.battlefield):
        if perm.controller_idx != player_idx or not perm.counters.pop(_WARP_EXILE, 0):
            continue
        zones.leave_battlefield(perm, Zone.EXILE, 'warp')
        details.append(f"warp exiled {perm.name}")
    return details
