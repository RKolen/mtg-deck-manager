"""Parse mana produced by lands from oracle text (Phase H)."""

from __future__ import annotations

import re

_COLOR_ORDER = 'WUBRG'
_MANA_TOKEN_RE = re.compile(r'\{([WRUBGC])\}')


def parse_produced_mana_from_oracle(
    oracle_text: str,
    *,
    type_line: str = '',
) -> list[str]:
    """Return mana colors a land produces, parsed from its oracle text."""
    if 'Land' not in type_line and 'land' not in (oracle_text or '').lower()[:30]:
        return []
    text = oracle_text or ''
    lowered = text.lower()
    if 'any color' in lowered or 'any one color' in lowered:
        return list(_COLOR_ORDER)

    colors: set[str] = set()
    for line in text.splitlines():
        if 'add' not in line.lower():
            continue
        for match in _MANA_TOKEN_RE.finditer(line):
            color = match.group(1)
            if color in _COLOR_ORDER:
                colors.add(color)
    return sorted(colors, key=_COLOR_ORDER.index)
