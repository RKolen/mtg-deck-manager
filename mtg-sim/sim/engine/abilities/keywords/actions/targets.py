"""Target permanent lookup for keyword actions."""

from __future__ import annotations

from engine.core.game_object import Permanent
from engine.core.zones import ZoneManager


def find_creature_by_uid(zones: ZoneManager, uid: str | None) -> Permanent | None:
    """Return a battlefield creature by string obj_id, or None."""
    if uid is None:
        return None
    try:
        return zones.find_permanent(int(uid))
    except ValueError:
        return None
