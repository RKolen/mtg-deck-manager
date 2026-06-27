"""Targeting keywords: Hexproof, Shroud, Ward, Protection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.abilities.keywords.other.hexproof_from import hexproof_from_qualities
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost

if TYPE_CHECKING:
    from deck_registry import CardInfo
    from engine.core.game_state import GameState

_PROTECTION_CLAUSE_RE = re.compile(
    r'protection from (?:the )?([\w]+)(?=\s|,|\.|$|and\b)',
    re.IGNORECASE,
)
_PROTECTION_AND_FROM_RE = re.compile(
    r'and from (?:the )?([\w]+)(?=\s|,|\.|$|and\b)',
    re.IGNORECASE,
)
_WARD_COST_RE = re.compile(r'ward\s*(\{[^}]+\})', re.IGNORECASE)
_DEFAULT_WARD_COST = "{2}"
_COLOR_ALIASES = {
    "w": "white",
    "u": "blue",
    "b": "black",
    "r": "red",
    "g": "green",
}
_COLOR_NAMES = frozenset(_COLOR_ALIASES.values())
_QUALITY_TYPE_MAP = {
    'creature': 'creatures',
    'creatures': 'creatures',
    'artifact': 'artifacts',
    'artifacts': 'artifacts',
    'enchantment': 'enchantments',
    'enchantments': 'enchantments',
    'instant': 'instants',
    'instants': 'instants',
    'sorcery': 'sorceries',
    'sorceries': 'sorceries',
    'colored': 'colored',
    'everything': 'everything',
}
_QUALITY_SOURCE_ATTR = {
    'creatures': 'is_creature',
    'artifacts': 'is_artifact',
    'enchantments': 'is_enchantment',
    'instants': 'is_instant',
    'sorceries': 'is_sorcery',
    'colored': 'is_colored',
}


@dataclass(frozen=True)
class ProtectionSource:
    """Traits of the spell or ability targeting a protected permanent."""

    is_creature: bool = False
    is_artifact: bool = False
    is_enchantment: bool = False
    is_instant: bool = False
    is_sorcery: bool = False
    colors: frozenset[str] = frozenset()

    @property
    def is_colored(self) -> bool:
        """True when the source is a colored spell (has colored mana in its cost)."""
        return bool(self.colors)


def has_hexproof(perm: Permanent) -> bool:
    """Return True when opponents cannot target this permanent."""
    return has_keyword(perm, 'Hexproof')


def has_shroud(perm: Permanent) -> bool:
    """Return True when no player can target this permanent."""
    return has_keyword(perm, 'Shroud')


def has_ward(perm: Permanent) -> bool:
    """Return True when the permanent has ward."""
    return has_keyword(perm, 'Ward')


def ward_cost(perm: Permanent) -> ManaCost:
    """Return the mana cost an opponent pays to target this permanent with ward."""
    match = _WARD_COST_RE.search(perm.oracle_text)
    if match is None:
        return ManaCost.parse(_DEFAULT_WARD_COST)
    return ManaCost.parse(match.group(1))


def must_pay_ward(source_controller_idx: int, target: Permanent) -> bool:
    """Return True when ward cost applies to this targeting relationship."""
    return has_ward(target) and source_controller_idx != target.controller_idx


def pay_ward_for_target(game: GameState, source_controller_idx: int, target: Permanent) -> bool:
    """Pay ward cost from the spell controller; return False if payment fails."""
    if not must_pay_ward(source_controller_idx, target):
        return True
    return game.players[source_controller_idx].mana_pool.pay(ward_cost(target))


def protection_qualities(perm: Permanent) -> frozenset[str]:
    """Return all protection qualities parsed from oracle text."""
    text = perm.oracle_text
    found = {
        _normalize_protection_quality(match.group(1))
        for match in _PROTECTION_CLAUSE_RE.finditer(text)
    }
    found.update(
        _normalize_protection_quality(match.group(1))
        for match in _PROTECTION_AND_FROM_RE.finditer(text)
    )
    if not found and has_keyword(perm, 'Protection'):
        return frozenset({'everything'})
    return frozenset(found)


def protection_source_from_card(card: CardInfo) -> ProtectionSource:
    """Build protection source traits from a card's type line and mana cost."""
    type_line = card.type_line
    parsed = ManaCost.parse(card.mana_cost or '')
    colors = frozenset(
        normalized
        for color in parsed.pips
        for normalized in (_normalize_protection_color(color),)
        if normalized in _COLOR_NAMES
    )
    return ProtectionSource(
        is_creature='Creature' in type_line,
        is_artifact='Artifact' in type_line,
        is_enchantment='Enchantment' in type_line,
        is_instant='Instant' in type_line,
        is_sorcery='Sorcery' in type_line,
        colors=colors,
    )


@dataclass(frozen=True)
class _SourceTypeFlags:
    is_creature: bool = False
    is_artifact: bool = False
    is_enchantment: bool = False
    is_instant: bool = False
    is_sorcery: bool = False


def protection_source_from_flags(
    types: _SourceTypeFlags | None = None,
    *,
    source_colors: frozenset[str] | None = None,
) -> ProtectionSource:
    """Build a ProtectionSource from type flags and optional colors."""
    flags = types or _SourceTypeFlags()
    normalized = frozenset(
        _normalize_protection_color(color) for color in (source_colors or frozenset())
    )
    return ProtectionSource(
        is_creature=flags.is_creature,
        is_artifact=flags.is_artifact,
        is_enchantment=flags.is_enchantment,
        is_instant=flags.is_instant,
        is_sorcery=flags.is_sorcery,
        colors=normalized,
    )


def _source_matches_protection_quality(source: ProtectionSource, quality: str) -> bool:
    """Return True when source matches a single protection quality."""
    if quality in {'everything', 'all'}:
        return True
    attr = _QUALITY_SOURCE_ATTR.get(quality)
    if attr is not None:
        return bool(getattr(source, attr))
    return quality in source.colors


def has_protection_from(perm: Permanent, source: ProtectionSource) -> bool:
    """Return True when protection on perm blocks targeting by source."""
    qualities = protection_qualities(perm)
    if not qualities:
        return False
    return any(_source_matches_protection_quality(source, quality) for quality in qualities)


def can_target_permanent(
    target: Permanent,
    controller_idx: int,
    *,
    source: ProtectionSource | None = None,
    source_card: CardInfo | None = None,
) -> bool:
    """Return True when controller_idx may target target with a spell or ability."""
    resolved = (
        protection_source_from_card(source_card)
        if source_card is not None
        else (source if source is not None else ProtectionSource())
    )
    hexproof_blocks = (
        has_hexproof(target) and controller_idx != target.controller_idx
    )
    hexproof_from_blocks = (
        controller_idx != target.controller_idx
        and any(
            _source_matches_protection_quality(resolved, quality)
            for quality in hexproof_from_qualities(target)
        )
    )
    return (
        not has_shroud(target)
        and not hexproof_blocks
        and not hexproof_from_blocks
        and not has_protection_from(target, resolved)
    )


def _normalize_protection_quality(text: str) -> str:
    """Normalize a protection clause to a canonical quality string."""
    lowered = text.strip().lower()
    if lowered.endswith(' and'):
        lowered = lowered[:-4].strip()
    if lowered in _COLOR_NAMES:
        return lowered
    return _QUALITY_TYPE_MAP.get(lowered, lowered)


def _normalize_protection_color(color: str) -> str:
    """Map mana letters and color names to protection quality strings."""
    lowered = color.lower()
    if len(lowered) == 1 and lowered in _COLOR_ALIASES:
        return _COLOR_ALIASES[lowered]
    return _normalize_protection_quality(lowered)
