#!/usr/bin/env python3
"""Regenerate keyword_registry_data.py from Scryfall catalog APIs (2026)."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

USER_AGENT = 'MTG-Deck-Manager/1.0'
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'sim' / 'engine' / 'abilities' / 'keyword_registry_data.py'

COMBAT_EVASION = {
    'flying', 'reach', 'menace', 'intimidate', 'fear', 'shadow',
    'islandwalk', 'swampwalk', 'mountainwalk', 'forestwalk', 'plainswalk',
    'legendary landwalk', 'nonbasic landwalk', 'landwalk',
}
COMBAT_DAMAGE = {
    'first strike', 'double strike', 'trample', 'deathtouch', 'lifelink',
}
COMBAT_PASSIVE = {'vigilance', 'defender'}
TIMING = {'haste', 'flash'}
TARGETING = {'hexproof', 'shroud', 'ward', 'protection'}
SURVIVAL = {'indestructible', 'regenerate'}
COUNTERS = {'wither', 'infect', 'persist', 'undying', 'modular'}
CASTING = {
    'flashback', 'escape', 'jump-start', 'aftermath', 'kicker', 'entwine',
    'overload', 'convoke', 'improvise', 'delve', 'cascade', 'storm', 'bestow',
    'miracle', 'replicate', 'buyback', 'retrace', 'emerge', 'mutate', 'foretell',
    'plot', 'spree', 'sneak', 'freerunning', 'madness', 'suspend',
}
ACTIVATED = {
    'equip', 'cycling', 'channel', 'crew', 'mount', 'unearth', 'level up',
}


def fetch_catalog(catalog: str) -> list[str]:
    """Return sorted catalog names from Scryfall."""
    url = f'https://api.scryfall.com/catalog/{catalog}'
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    return sorted(payload['data'], key=str.lower)


def categorize(name: str, kind: str) -> str:
    """Assign a rules hook category for engine integration."""
    key = name.lower()
    if kind == 'action':
        return 'action'
    if kind == 'word':
        return 'ability_word'
    if key in COMBAT_EVASION or key.endswith('walk'):
        return 'combat_evasion'
    if key in COMBAT_DAMAGE:
        return 'combat_damage'
    if key in COMBAT_PASSIVE:
        return 'combat_passive'
    if key in TIMING:
        return 'timing'
    if key in TARGETING or 'protection' in key:
        return 'targeting'
    if key in SURVIVAL:
        return 'survival'
    if key in COUNTERS:
        return 'counters'
    if key in CASTING:
        return 'casting'
    if key in ACTIVATED or 'equip' in key or 'cycling' in key:
        return 'activated'
    return 'ability_other'


def main() -> None:
    """Write keyword_registry_data.py."""
    try:
        abilities = fetch_catalog('keyword-abilities')
        actions = fetch_catalog('keyword-actions')
        words = fetch_catalog('ability-words')
    except OSError as exc:
        print(f'Failed to fetch Scryfall catalogs: {exc}')
        print('Keep the existing keyword_registry_data.py or retry with network access.')
        raise SystemExit(1) from exc
    entries: list[tuple[str, str, str]] = []
    for name in abilities:
        entries.append((name, 'ability', categorize(name, 'ability')))
    for name in actions:
        entries.append((name, 'action', categorize(name, 'action')))
    for name in words:
        entries.append((name, 'word', categorize(name, 'word')))

    lines = [
        '"""Scryfall keyword catalog (abilities, actions, ability words).',
        '',
        'Generated from api.scryfall.com/catalog/* (Scryfall database as of generator run).',
        'Regenerate: python scripts/generate_keyword_registry.py',
        '"""',
        '',
        'from __future__ import annotations',
        '',
        '# (display_name, kind, category)',
        '# kind: ability | action | word',
        'KEYWORD_ENTRIES: tuple[tuple[str, str, str], ...] = (',
    ]
    for name, kind, category_name in entries:
        lines.append(f'    ({name!r}, {kind!r}, {category_name!r}),')
    lines.append(')')
    lines.append('')
    lines.append(f'SCRYFALL_KEYWORD_COUNT = {len(entries)}')
    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Wrote {len(entries)} keywords to {OUT}')


if __name__ == '__main__':
    main()
