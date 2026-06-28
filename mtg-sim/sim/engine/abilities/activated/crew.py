"""Crew: tap creatures with total power at least crew cost (CR 702.122, simplified)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.rules.combat import power

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_CREW_RE = re.compile(r"crew\s*(\d+)", re.IGNORECASE)
_CREWED_COUNTER = "crewed"


def has_crew(perm: Permanent) -> bool:
    """Return True when the permanent is a vehicle with crew."""
    return "Vehicle" in perm.type_line and (
        has_registered_keyword(perm.oracle_text, "Crew")
        or bool(_CREW_RE.search(perm.oracle_text))
    )


def has_crew_card(card: CardInfo) -> bool:
    """Return True when the card is a vehicle with crew."""
    if "Vehicle" not in (card.type_line or ""):
        return False
    oracle = card.oracle_text or ""
    return has_registered_keyword(oracle, "Crew") or bool(_CREW_RE.search(oracle))


def crew_cost(perm: Permanent) -> int:
    """Return the crew number from oracle text."""
    match = _CREW_RE.search(perm.oracle_text)
    if match is None:
        return 0
    return int(match.group(1))


def is_crewed_vehicle(perm: Permanent) -> bool:
    """Return True when a vehicle has been crewed this turn."""
    return "Vehicle" in perm.type_line and perm.counters.get(_CREWED_COUNTER, 0) > 0


def can_crew(
    vehicle: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when the vehicle may be crewed now."""
    if not has_crew(vehicle) or vehicle.controller_idx != controller_idx:
        return False
    if phase not in ("main1", "main2") or not game.stack.is_empty:
        return False
    return not vehicle.tapped


def _crewer_validation_error(
    game: GameState,
    controller_idx: int,
    uid: str,
) -> str | None:
    """Return an error when a single crewer is illegal."""
    perm = _find_perm(game, uid)
    if perm is None:
        return f"Crewer {uid} not found"
    if perm.controller_idx != controller_idx:
        return f"{perm.name} cannot crew"
    if "Creature" not in perm.type_line:
        return f"{perm.name} is not a creature"
    if perm.tapped:
        return f"{perm.name} is already tapped"
    return None


def crew_power_error(
    game: GameState,
    controller_idx: int,
    crewer_ids: list[str],
    required: int,
) -> str | None:
    """Return an error when tapped crewers do not meet the crew requirement."""
    if required <= 0:
        return "Invalid crew cost"
    total = 0
    for uid in crewer_ids:
        err = _crewer_validation_error(game, controller_idx, uid)
        if err is not None:
            return err
        perm = _find_perm(game, uid)
        assert perm is not None
        total += power(perm)
    if total < required:
        return f"Need crew power {required}, have {total}"
    return None


def _find_perm(game: GameState, uid: str) -> Permanent | None:
    for perm in game.zones.battlefield:
        if str(perm.obj_id) == uid:
            return perm
    return None


def apply_crew(
    game: GameState,
    vehicle: Permanent,
    crewer_ids: list[str],
) -> None:
    """Tap crewers and mark the vehicle as crewed (after crew_power_error passes)."""
    required = crew_cost(vehicle)
    for uid in crewer_ids:
        perm = _find_perm(game, uid)
        assert perm is not None
        perm.tapped = True
    vehicle.counters[_CREWED_COUNTER] = required
    vehicle.sick = False
