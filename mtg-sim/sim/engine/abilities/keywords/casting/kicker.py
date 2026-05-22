"""Kicker and multikicker: optional additional costs and kicked effects."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.registry import has_registered_keyword
from engine.cards.oracle_parse import parse_damage, parse_pump
from engine.core.mana import ManaCost

_KICKER_COST_RE = re.compile(
    r'(?:multi)?kicker\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_KICKED_DAMAGE_RE = re.compile(
    r'if (?:this spell )?was kicked.*?deals (\d+) damage',
    re.IGNORECASE | re.DOTALL,
)
_KICKED_DAMAGE_INSTEAD_RE = re.compile(
    r'deals (\d+) damage instead',
    re.IGNORECASE,
)
_KICKED_DRAW_RE = re.compile(
    r'if (?:this spell )?was kicked.*?draw (\w+) card',
    re.IGNORECASE | re.DOTALL,
)
_KICKED_PUMP_RE = re.compile(
    r'if (?:this spell )?was kicked.*?gets? \+(\d+)/\+(\d+)',
    re.IGNORECASE | re.DOTALL,
)
_KICKED_COUNTER_RE = re.compile(
    r'if (?:this spell )?was kicked.*?with (\w+) \+1/\+1 counter',
    re.IGNORECASE | re.DOTALL,
)
_WORD_TO_INT = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4}


def has_kicker(card: CardInfo) -> bool:
    """Return True when the card has kicker or multikicker."""
    text = card.oracle_text or ''
    return (
        has_registered_keyword(text, 'Kicker')
        or has_registered_keyword(text, 'Multikicker')
        or bool(_KICKER_COST_RE.search(text))
    )


def is_multikicker(card: CardInfo) -> bool:
    """Return True when the card has multikicker (may be paid multiple times)."""
    text = (card.oracle_text or '').lower()
    return 'multikicker' in text or has_registered_keyword(text, 'Multikicker')


def kicker_cost(card: CardInfo) -> ManaCost | None:
    """Parse the kicker or multikicker cost from oracle text."""
    match = _KICKER_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def kicker_mana_per_time(card: CardInfo) -> int:
    """Return generic mana lands to tap for each kicker payment (simplified)."""
    cost = kicker_cost(card)
    return cost.mana_value if cost is not None else 0


def normalize_kicker_times(card: CardInfo, kicker_times: int) -> int:
    """Clamp kicker payments to legal values for this card."""
    if kicker_times <= 0:
        return 0
    if not has_kicker(card):
        return 0
    if is_multikicker(card):
        return max(0, kicker_times)
    return 1


def cast_mana_needed(card: CardInfo, kicker_times: int) -> tuple[int, int]:
    """Return total mana and life for a cast with optional kicker payments."""
    phyrexian_pips = (card.mana_cost or '').upper().count('/P')
    total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
    base = max(0, total_cmc - phyrexian_pips)
    life = phyrexian_pips * 2
    times = normalize_kicker_times(card, kicker_times)
    return base + kicker_mana_per_time(card) * times, life


def spell_damage(card: CardInfo, kicker_times: int) -> int:
    """Resolve burn damage including kicked replacements."""
    oracle = card.oracle_text or ''
    base = parse_damage(oracle) or max(1, int(card.cmc))
    if normalize_kicker_times(card, kicker_times) < 1:
        return base
    kicked = _kicked_damage(oracle)
    return kicked if kicked is not None else base


def extra_draw_from_kicker(card: CardInfo, kicker_times: int) -> int:
    """Return additional cards drawn when a kicked draw spell resolves."""
    if normalize_kicker_times(card, kicker_times) < 1:
        return 0
    oracle = card.oracle_text or ''
    match = _KICKED_DRAW_RE.search(oracle)
    if match is None:
        return 0
    word = match.group(1).lower()
    return _WORD_TO_INT.get(word, int(word) if word.isdigit() else 1)


def kicked_pump_bonus(card: CardInfo, kicker_times: int) -> tuple[int, int]:
    """Return +power/+toughness from a kicked pump clause, or (0, 0)."""
    if normalize_kicker_times(card, kicker_times) < 1:
        return 0, 0
    match = _KICKED_PUMP_RE.search(card.oracle_text or '')
    if match is None:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def kicked_counter_count(card: CardInfo, kicker_times: int) -> int:
    """Return +1/+1 counters for a kicked creature spell."""
    times = normalize_kicker_times(card, kicker_times)
    if times < 1:
        return 0
    match = _KICKED_COUNTER_RE.search(card.oracle_text or '')
    if match is None:
        return 0
    word = match.group(1).lower()
    per_kick = _WORD_TO_INT.get(word, int(word) if word.isdigit() else 1)
    return per_kick * times if is_multikicker(card) else per_kick


def pump_with_kicker(card: CardInfo, kicker_times: int) -> tuple[int, int]:
    """Return pump stats from base oracle plus any kicked bonus."""
    power, toughness = parse_pump(card.oracle_text or '')
    bonus_power, bonus_toughness = kicked_pump_bonus(card, kicker_times)
    if bonus_power or bonus_toughness:
        return bonus_power, bonus_toughness
    if power == 0 and toughness == 0 and normalize_kicker_times(card, kicker_times) >= 1:
        return 1, 1
    return power, toughness


def _kicked_damage(oracle: str) -> int | None:
    """Parse the damage dealt when a burn spell was kicked."""
    match = _KICKED_DAMAGE_RE.search(oracle)
    if match is not None:
        return int(match.group(1))
    match = _KICKED_DAMAGE_INSTEAD_RE.search(oracle)
    if match is not None:
        return int(match.group(1))
    return None
