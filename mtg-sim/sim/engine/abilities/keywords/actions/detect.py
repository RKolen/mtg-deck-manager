"""Detection helpers for the 72 Scryfall keyword actions."""

from __future__ import annotations

import re

from engine.abilities.keywords.registry import (
    entries_by_length,
    has_registered_keyword,
    keywords_by_category,
)

ALL_KEYWORD_ACTIONS: tuple[str, ...] = keywords_by_category('action')


def has_keyword_action(oracle_text: str | None, action_name: str) -> bool:
    """Return True when a keyword action verb appears in oracle text."""
    return has_registered_keyword(oracle_text, action_name)


def keyword_actions_in_oracle(oracle_text: str | None) -> tuple[str, ...]:
    """Return keyword action names in left-to-right oracle order."""
    if not oracle_text:
        return ()
    lowered = oracle_text.lower()
    hits: list[tuple[int, str]] = []
    for entry in entries_by_length():
        if entry.kind != 'action':
            continue
        escaped = re.escape(entry.key)
        for match in re.finditer(rf'\b{escaped}\b', lowered):
            hits.append((match.start(), entry.name))
    hits.sort(key=lambda item: item[0])
    seen: set[str] = set()
    ordered: list[str] = []
    for _, name in hits:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)
