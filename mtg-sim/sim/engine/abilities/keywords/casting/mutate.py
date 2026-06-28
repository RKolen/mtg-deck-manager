"""Mutate: cast a creature for its mutate cost onto a non-Human host (CR 702.139)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.alt_cost_mana import alt_cost_mana_needed
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost
from engine.core.zones import ZoneManager

_MUTATE_COST_RE = re.compile(
    r'mutate\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)


def has_mutate(card: CardInfo) -> bool:
    """Return True when the creature may be cast for its mutate cost."""
    if not card.is_creature:
        return False
    return has_registered_keyword(card.oracle_text, 'Mutate') or bool(
        _MUTATE_COST_RE.search(card.oracle_text or '')
    )


def has_mutate_card(card: CardInfo) -> bool:
    """Return True when the card has mutate."""
    return has_mutate(card)


def mutate_cost(card: CardInfo) -> ManaCost | None:
    """Parse the mutate alternate cost from oracle text."""
    match = _MUTATE_COST_RE.search(card.oracle_text or '')
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def mutate_mana_needed(card: CardInfo) -> tuple[int, int]:
    """Return mana and life to pay the mutate cost instead of the mana cost."""
    return alt_cost_mana_needed(mutate_cost(card), card)


def requires_non_human_host(card: CardInfo) -> bool:
    """Return True when mutate may only target non-Human creatures."""
    return 'non-human' in (card.oracle_text or '').lower()


def normalize_mutate_cast(card: CardInfo, cast_for_mutate: bool, host_uid: str | None) -> bool:
    """Return whether this cast uses mutate."""
    if not cast_for_mutate or not host_uid:
        return False
    return has_mutate(card)


def mutate_host_error(
    zones: ZoneManager,
    player_idx: int,
    card: CardInfo,
    host_uid: str | None,
) -> str | None:
    """Return an error message when the mutate host is illegal."""
    message: str | None = None
    if host_uid:
        try:
            host_id = int(host_uid)
        except ValueError:
            message = "Invalid mutate target"
        else:
            host = zones.find_permanent(host_id)
            if host is None:
                message = f"Mutate host {host_id} not found"
            elif host.controller_idx != player_idx:
                message = "Mutate may only target creatures you control"
            elif 'Creature' not in host.type_line:
                message = f"{host.name} is not a creature"
            elif requires_non_human_host(card) and _is_human_creature(host):
                message = f"{host.name} is Human"
    return message


def mutate_bonus_counters(card: CardInfo) -> int:
    """Return +1/+1 counters to add to the host when a mutate spell resolves."""
    power = card.numeric_power
    toughness = card.numeric_toughness
    return max(1, power + toughness)


def _is_human_creature(host: Permanent) -> bool:
    """Return True when the permanent is a Human creature."""
    return 'Human' in host.type_line
