"""Affinity: each artifact you control reduces generic mana by one."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.zones import ZoneManager

_AFFINITY_ARTIFACTS_RE = re.compile(
    r'affinity\s+for\s+artifacts',
    re.IGNORECASE,
)


def has_affinity_for_artifacts(oracle_text: str | None) -> bool:
    """Return True when the card has affinity for artifacts."""
    text = oracle_text or ''
    return (
        has_registered_keyword(text, 'Affinity')
        and bool(_AFFINITY_ARTIFACTS_RE.search(text))
    )


def has_affinity_card(card: CardInfo) -> bool:
    """Return True when the card has affinity for artifacts."""
    return has_affinity_for_artifacts(card.oracle_text)


def artifact_count(zones: ZoneManager, controller_idx: int) -> int:
    """Count artifacts controlled by a player."""
    return sum(
        1
        for perm in zones.battlefield
        if perm.controller_idx == controller_idx and 'Artifact' in perm.type_line
    )


def affinity_reduction(
    card: CardInfo,
    zones: ZoneManager,
    controller_idx: int,
) -> int:
    """Return mana discount from affinity for artifacts."""
    if not has_affinity_for_artifacts(card.oracle_text):
        return 0
    return artifact_count(zones, controller_idx)
