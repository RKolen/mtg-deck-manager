"""Changeling: this card is every creature type."""

from __future__ import annotations

import re

from dataclasses import dataclass

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent

_SUBTYPE_RE = re.compile(r'creature\s*[—–-]\s*([^\n]+)', re.IGNORECASE)


def has_changeling(perm: Permanent) -> bool:
    """Return True when the permanent has changeling."""
    return has_keyword(perm, 'Changeling')


def oracle_has_changeling(oracle_text: str | None) -> bool:
    """Return True when oracle text includes changeling."""
    return has_registered_keyword(oracle_text, 'Changeling')


@dataclass(frozen=True)
class CreatureTypeRef:
    """Type line plus optional changeling sources."""

    type_line: str
    perm: Permanent | None = None
    oracle: str | None = None


def creature_subtypes(type_line: str) -> set[str]:
    """Return creature subtypes from a type line."""
    match = _SUBTYPE_RE.search(type_line or '')
    if match is None:
        return set()
    return {part.strip().lower() for part in match.group(1).split() if part.strip()}


def shares_creature_type(left: CreatureTypeRef, right: CreatureTypeRef) -> bool:
    """Return True when two creatures share a creature type (changeling matches all)."""
    if (left.perm is not None and has_changeling(left.perm)) or oracle_has_changeling(left.oracle):
        return 'Creature' in right.type_line
    if (right.perm is not None and has_changeling(right.perm)) or oracle_has_changeling(
        right.oracle,
    ):
        return 'Creature' in left.type_line
    left_types = creature_subtypes(left.type_line)
    right_types = creature_subtypes(right.type_line)
    return bool(left_types and right_types and left_types & right_types)
