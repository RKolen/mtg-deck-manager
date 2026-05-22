"""Detection helpers for Scryfall ability words."""

from __future__ import annotations

from engine.abilities.keywords.registry import has_registered_keyword, keywords_by_category

ALL_ABILITY_WORDS: tuple[str, ...] = keywords_by_category('ability_word')


def has_ability_word(oracle_text: str | None, word: str) -> bool:
    """Return True when an ability word appears in oracle text."""
    return has_registered_keyword(oracle_text, word)
