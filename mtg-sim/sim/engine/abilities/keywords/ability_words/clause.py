"""Parse triggered clauses that follow an ability word."""

from __future__ import annotations

import re


def clause_after_ability_word(oracle_text: str, word: str) -> str:
    """Return the effect text after 'Landfall —' / 'Raid —' style lines."""
    pattern = rf'\b{re.escape(word)}\s*[—–-]\s*(.+?)(?:\n\n|\Z)'
    match = re.search(pattern, oracle_text, re.IGNORECASE | re.DOTALL)
    if match is None:
        return ''
    return match.group(1).strip()
