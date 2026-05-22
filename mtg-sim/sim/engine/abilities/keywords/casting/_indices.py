"""Shared index normalization for graveyard payments."""

from __future__ import annotations


def normalize_unique_indices(indices: list[int]) -> list[int]:
    """Return deduplicated indices preserving first-seen order."""
    if not indices:
        return []
    seen: set[int] = set()
    unique: list[int] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            unique.append(idx)
    return unique
