"""Banding: combat damage assignment modifier (CR 702.22, simplified)."""

from __future__ import annotations

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent


def has_banding(perm: Permanent) -> bool:
    """Return True when the permanent has banding."""
    return has_keyword(perm, 'Banding')


def bands_with_other(perm: Permanent) -> bool:
    """Return True when the permanent has bands with other."""
    text = (perm.oracle_text or '').lower()
    return 'bands with other' in text


def attacking_band_size(attackers: list[Permanent]) -> int:
    """Return the number of banding creatures in an attack."""
    return sum(1 for perm in attackers if has_banding(perm) or bands_with_other(perm))


def blocker_uses_banding_assignment(blocker: Permanent) -> bool:
    """Return True when a blocker may assign combat damage via banding."""
    return has_banding(blocker) or bands_with_other(blocker)


def banding_block_detail(blocker: Permanent, attacker: Permanent) -> str | None:
    """Return a log line when banding changes damage assignment."""
    if not blocker_uses_banding_assignment(blocker):
        return None
    return f"banding {blocker.name} assigns damage from {attacker.name}"
