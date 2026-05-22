"""
Scryfall-backed keyword registry for all MTG keywords (2026).

Detection scans oracle text against every name in KEYWORD_ENTRIES (359 entries
from Scryfall catalogs: keyword-abilities, keyword-actions, ability-words).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TypedDict

from engine.abilities.keyword_registry_data import KEYWORD_ENTRIES, SCRYFALL_KEYWORD_COUNT
from engine.core.game_object import oracle_has_keyword

KeywordKind = str  # ability | action | word
KeywordCategory = str


class RegistrySummary(TypedDict):
    """Counts returned by registry_summary()."""

    total: int
    by_kind: dict[str, int]
    by_category: dict[str, int]


@dataclass(frozen=True)
class KeywordEntry:
    """One Scryfall keyword with engine hook category."""

    name: str
    kind: KeywordKind
    category: KeywordCategory

    @property
    def key(self) -> str:
        """Normalized lookup key."""
        return self.name.lower()


@lru_cache(maxsize=1)
def all_entries() -> tuple[KeywordEntry, ...]:
    """Return every registered keyword entry."""
    return tuple(
        KeywordEntry(name=name, kind=kind, category=category)
        for name, kind, category in KEYWORD_ENTRIES
    )


@lru_cache(maxsize=1)
def entries_by_length() -> tuple[KeywordEntry, ...]:
    """Return entries sorted longest-first for overlapping substring detection."""
    return tuple(sorted(all_entries(), key=lambda entry: len(entry.name), reverse=True))


@lru_cache(maxsize=1)
def entry_by_key() -> dict[str, KeywordEntry]:
    """Map normalized keyword name to entry."""
    return {entry.key: entry for entry in all_entries()}


def canonical_name(name: str) -> str | None:
    """Return Scryfall display name for a case-insensitive keyword name."""
    entry = entry_by_key().get(name.lower())
    return entry.name if entry is not None else None


def _oracle_matches(entry: KeywordEntry, oracle_lower: str) -> bool:
    """Return True when entry name appears in oracle text."""
    escaped = re.escape(entry.key)
    if entry.kind == 'action' or len(entry.key) <= 6:
        return re.search(rf'\b{escaped}\b', oracle_lower) is not None
    return entry.key in oracle_lower


def detect_keywords(oracle_text: str | None) -> frozenset[str]:
    """Return all Scryfall keywords present in oracle text."""
    if not oracle_text:
        return frozenset()
    lowered = oracle_text.lower()
    found: set[str] = set()
    for entry in entries_by_length():
        if _oracle_matches(entry, lowered):
            found.add(entry.name)
    return frozenset(found)


def has_registered_keyword(oracle_text: str | None, keyword: str) -> bool:
    """Return True when keyword (any casing) appears in oracle text."""
    if not oracle_text:
        return False
    canonical = canonical_name(keyword)
    if canonical is None:
        return oracle_has_keyword(oracle_text, keyword)
    return canonical.lower() in oracle_text.lower()


def keywords_by_category(category: KeywordCategory) -> tuple[str, ...]:
    """Return display names for one hook category."""
    return tuple(entry.name for entry in all_entries() if entry.category == category)


def registry_summary() -> RegistrySummary:
    """Return counts by kind and category for diagnostics."""
    by_kind: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for entry in all_entries():
        by_kind[entry.kind] = by_kind.get(entry.kind, 0) + 1
        by_category[entry.category] = by_category.get(entry.category, 0) + 1
    return RegistrySummary(
        total=SCRYFALL_KEYWORD_COUNT,
        by_kind=by_kind,
        by_category=by_category,
    )


# Re-export catalog symbols for callers that import from this module.
__all__ = [
    'KEYWORD_ENTRIES',
    'SCRYFALL_KEYWORD_COUNT',
    'KeywordEntry',
    'RegistrySummary',
    'all_entries',
    'canonical_name',
    'detect_keywords',
    'entries_by_length',
    'entry_by_key',
    'has_registered_keyword',
    'keywords_by_category',
    'registry_summary',
]
