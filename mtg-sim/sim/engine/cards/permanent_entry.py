"""Battlefield entry setup for auras and planeswalkers (Phase H)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.actions._parse import word_to_int
from engine.abilities.keywords.other.enchant import can_enchant_target, has_enchant
from engine.core.game_object import Permanent
from engine.core.zones import ZoneManager

_STARTING_LOYALTY_RE = re.compile(
    r'(?:enters|enter)s? the battlefield with (\w+) loyalty counters?',
    re.IGNORECASE,
)


def is_aura(card: CardInfo) -> bool:
    """Return True when the card is an Aura enchantment."""
    return 'Aura' in (card.type_line or '')


def is_planeswalker(card: CardInfo) -> bool:
    """Return True when the card is a planeswalker."""
    return 'Planeswalker' in (card.type_line or '')


def starting_loyalty(oracle_text: str) -> int:
    """Parse how many loyalty counters a planeswalker enters with."""
    match = _STARTING_LOYALTY_RE.search(oracle_text or '')
    if match is None:
        return 0
    return word_to_int(match.group(1))


def apply_planeswalker_entry(permanent: Permanent) -> int:
    """Set starting loyalty counters when a planeswalker enters."""
    loyalty = starting_loyalty(permanent.oracle_text)
    if loyalty > 0:
        permanent.counters['loyalty'] = loyalty
    return loyalty


def attach_aura(permanent: Permanent, host: Permanent | None) -> str | None:
    """Attach an Aura to its host permanent."""
    if host is None:
        return None
    permanent.attached_to = host.obj_id
    return f'{permanent.name} attached to {host.name}'


def _aura_host_error(
    card: CardInfo,
    zones: ZoneManager,
    controller_idx: int,
    target_uid_str: str,
) -> str | None:
    """Validate the enchant host for an Aura cast."""
    try:
        host_id = int(target_uid_str)
    except ValueError:
        return 'Invalid enchant target'
    host = zones.find_permanent(host_id)
    if host is None:
        return 'Enchant target not found'
    if host.controller_idx != controller_idx:
        return 'Enchant target must be a permanent you control'
    if not can_enchant_target(card.oracle_text or '', host):
        return f'{card.name} cannot enchant {host.name}'
    return None


def aura_target_error(
    card: CardInfo,
    zones: ZoneManager,
    controller_idx: int,
    target_uid_str: str | None,
) -> str | None:
    """Return an error when an Aura cast lacks or has an illegal enchant target."""
    if not is_aura(card) or not has_enchant(card):
        return None
    if not target_uid_str:
        return f'{card.name} requires an enchant target'
    return _aura_host_error(card, zones, controller_idx, target_uid_str)
