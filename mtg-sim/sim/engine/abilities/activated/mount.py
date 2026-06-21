"""Mount: tap creatures with total power at least mount cost (CR 702.166, simplified)."""

from __future__ import annotations

import re

from engine.abilities.activated.crew import (
    _CREWED_COUNTER,
    _find_perm,
    crew_power_error,
)
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState

_MOUNT_RE = re.compile(r"mount\s*(\d+)", re.IGNORECASE)


def has_mount(perm: Permanent) -> bool:
    """Return True when the permanent is a mount with mount."""
    return "Mount" in perm.type_line and (
        has_registered_keyword(perm.oracle_text, "Mount")
        or bool(_MOUNT_RE.search(perm.oracle_text))
    )


def mount_cost(perm: Permanent) -> int:
    """Return the mount number from oracle text."""
    match = _MOUNT_RE.search(perm.oracle_text)
    if match is None:
        return 0
    return int(match.group(1))


def is_mounted(perm: Permanent) -> bool:
    """Return True when a mount has been mounted this turn."""
    return "Mount" in perm.type_line and perm.counters.get(_CREWED_COUNTER, 0) > 0


def can_mount(
    mount: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when the mount may be mounted now."""
    if not has_mount(mount) or mount.controller_idx != controller_idx:
        return False
    if phase not in ("main1", "main2") or not game.stack.is_empty:
        return False
    return not mount.tapped


def mount_power_error(
    game: GameState,
    controller_idx: int,
    mount_creature_ids: list[str],
    required: int,
) -> str | None:
    """Return an error when tapped creatures do not meet the mount requirement."""
    return crew_power_error(game, controller_idx, mount_creature_ids, required)


def apply_mount(
    game: GameState,
    mount_perm: Permanent,
    mount_creature_ids: list[str],
) -> None:
    """Tap creatures and mark the mount as mounted."""
    required = mount_cost(mount_perm) or 1
    for uid in mount_creature_ids:
        perm = _find_perm(game, uid)
        assert perm is not None
        perm.tapped = True
    mount_perm.counters[_CREWED_COUNTER] = required
    mount_perm.sick = False
