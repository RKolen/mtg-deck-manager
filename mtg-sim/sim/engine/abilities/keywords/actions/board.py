"""Board-affecting keyword actions: Tap, Untap, Sacrifice."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.actions.detect import has_keyword_action
from engine.abilities.keywords.actions.targets import find_creature_by_uid
from engine.core.zones import Zone, ZoneManager

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_tap_action(oracle_text: str | None) -> bool:
    """Return True when oracle uses Tap as a keyword action (not reminder text)."""
    if not has_keyword_action(oracle_text, 'Tap'):
        return False
    lowered = (oracle_text or '').lower()
    return 'tap target' in lowered


def has_untap_action(oracle_text: str | None) -> bool:
    """Return True when oracle uses Untap as a keyword action."""
    if not has_keyword_action(oracle_text, 'Untap'):
        return False
    lowered = (oracle_text or '').lower()
    return 'untap target' in lowered


def has_sacrifice_action(oracle_text: str | None) -> bool:
    """Return True when oracle uses Sacrifice as a keyword action."""
    if not has_keyword_action(oracle_text, 'Sacrifice'):
        return False
    lowered = (oracle_text or '').lower()
    return 'sacrifice target' in lowered


def tap_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Tap target creature."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.tapped = True
    return f"tapped {target.name}"


def untap_creature(zones: ZoneManager, target_uid: str | None) -> str | None:
    """Untap target creature."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    target.tapped = False
    return f"untapped {target.name}"


def sacrifice_creature(
    zones: ZoneManager,
    game: GameState,
    target_uid: str | None,
) -> str | None:
    """Sacrifice target creature."""
    target = find_creature_by_uid(zones, target_uid)
    if target is None:
        return None
    zones.leave_battlefield(target, Zone.GRAVEYARD, 'sacrifice', game)
    return f"sacrificed {target.name}"
