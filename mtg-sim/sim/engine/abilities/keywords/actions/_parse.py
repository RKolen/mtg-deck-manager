"""Shared parsers for Scryfall keyword action amounts."""

from __future__ import annotations

import re

_WORD_TO_INT: dict[str, int] = {
    'a': 1,
    'an': 1,
    'one': 1,
    'two': 2,
    'three': 3,
    'four': 4,
    'five': 5,
    'six': 6,
    'seven': 7,
    'eight': 8,
    'nine': 9,
    'ten': 10,
}


def word_to_int(word: str) -> int:
    """Convert an English number word or digit string to int."""
    key = word.lower()
    if key.isdigit():
        return int(key)
    return _WORD_TO_INT.get(key, 1)


def parse_amount_after_keyword(text: str, keyword: str) -> int:
    """Return N from phrases like 'Mill two' or 'Scry 1' (default 1)."""
    pattern = rf'\b{re.escape(keyword)}\s+(\w+|\d+)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match is None:
        return 1
    return word_to_int(match.group(1))


def parse_target_player_mill(text: str) -> int:
    """Return N from 'target player mills two' / 'target opponent mills'."""
    match = re.search(
        r'target (?:player|opponent) mills (\w+|\d+)',
        text,
        re.IGNORECASE,
    )
    if match is None:
        return 0
    return word_to_int(match.group(1))


def parse_each_player_mill(text: str) -> int:
    """Return N from 'each player mills two'."""
    match = re.search(
        r'each player mills (\w+|\d+)',
        text,
        re.IGNORECASE,
    )
    if match is None:
        return 0
    return word_to_int(match.group(1))
