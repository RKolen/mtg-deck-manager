"""Improvise: tap artifacts you control to help pay generic mana (CR 702.132, simplified)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.zones import ZoneManager


def has_improvise(card: CardInfo) -> bool:
    """Return True when the card has improvise."""
    return has_registered_keyword(card.oracle_text, 'Improvise')


def has_improvise_card(card: CardInfo) -> bool:
    """Return True when the card has improvise."""
    return has_improvise(card)


def normalize_improvise_artifact_ids(
    card: CardInfo,
    artifact_ids: list[int],
) -> list[int]:
    """Return deduped artifact ids when improvise applies; otherwise []."""
    if not artifact_ids or not has_improvise(card):
        return []
    seen: set[int] = set()
    unique: list[int] = []
    for obj_id in artifact_ids:
        if obj_id not in seen:
            seen.add(obj_id)
            unique.append(obj_id)
    return unique


def improvise_tap_error(
    zones: ZoneManager,
    player_idx: int,
    artifact_ids: list[int],
) -> str | None:
    """Return an error message when improvise taps are illegal."""
    for obj_id in artifact_ids:
        perm = zones.find_permanent(obj_id)
        if perm is None:
            return f"Improvise artifact {obj_id} not found"
        if perm.controller_idx != player_idx:
            return "Improvise may only tap artifacts you control"
        if perm.tapped:
            return f"{perm.name} is already tapped"
        if "Artifact" not in perm.type_line:
            return f"{perm.name} is not an artifact"
    return None


def tap_improvise_artifacts(zones: ZoneManager, artifact_ids: list[int]) -> None:
    """Tap permanents chosen for improvise (call only after improvise_tap_error passes)."""
    for obj_id in artifact_ids:
        perm = zones.find_permanent(obj_id)
        assert perm is not None
        perm.tapped = True


def resolve_improvise_for_cast(
    card: CardInfo,
    mana_needed: int,
    raw_artifact_ids: list[int],
    zones: ZoneManager,
    player_idx: int,
) -> tuple[int, list[int], str | None]:
    """Apply improvise: validate, tap artifacts, return remaining land mana and ids."""
    if raw_artifact_ids and not has_improvise(card):
        return mana_needed, [], f"{card.name} does not have improvise"
    improvise_ids = normalize_improvise_artifact_ids(card, raw_artifact_ids)
    if not improvise_ids:
        return mana_needed, [], None
    capped = (
        improvise_ids[:mana_needed]
        if mana_needed < len(improvise_ids)
        else improvise_ids
    )
    err = improvise_tap_error(zones, player_idx, capped)
    if err is not None:
        return mana_needed, [], err
    tap_improvise_artifacts(zones, capped)
    return max(0, mana_needed - len(capped)), capped, None
