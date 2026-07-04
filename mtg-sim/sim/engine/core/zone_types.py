"""Zone enum shared without importing ZoneManager (avoids import cycles)."""

from __future__ import annotations

import enum


class Zone(enum.Enum):
    """All zones defined by the MTG Comprehensive Rules (CR 400.1)."""

    LIBRARY = "library"
    HAND = "hand"
    BATTLEFIELD = "battlefield"
    GRAVEYARD = "graveyard"
    EXILE = "exile"
    STACK = "stack"
    COMMAND = "command"
