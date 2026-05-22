"""Shared keyword helpers used across category modules."""

from __future__ import annotations

from engine.abilities.keywords.registry import detect_keywords, has_registered_keyword
from engine.core.game_object import Permanent


def has_keyword(perm: Permanent, keyword: str) -> bool:
    """Return True when the permanent's oracle text contains keyword."""
    return has_registered_keyword(perm.oracle_text, keyword)


def list_keywords(perm: Permanent) -> frozenset[str]:
    """Return every Scryfall keyword detected on this permanent."""
    return detect_keywords(perm.oracle_text)


def is_creature(perm: Permanent) -> bool:
    """Return True when the permanent is a creature."""
    return 'Creature' in perm.type_line


def is_artifact_creature(perm: Permanent) -> bool:
    """Return True when the permanent is an artifact creature."""
    return 'Artifact' in perm.type_line and 'Creature' in perm.type_line
