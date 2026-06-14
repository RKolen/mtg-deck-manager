"""Offering: sacrifice a creature to cast an artifact (simplified)."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.casting.sacrifice_creature import (
    CreatureSacrificeCastCheck,
    CreatureSacrificeCost,
    make_creature_sacrifice_cast_error,
    sacrifice_creature_for_cast_cost,
)
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState
from engine.core.zones import ZoneManager

_OFFERING_RE = re.compile(r'offering\s*((?:\{[^}]+\})+)?', re.IGNORECASE)
_OFFERING_REDUCTION = 2
_OFFERING_COST = CreatureSacrificeCost(
    label='offering',
    missing_message='Offering requires sacrificing a creature',
    not_found_fmt='Offering sacrifice {sacrifice_id} not found',
    wrong_controller_message='Offering may only sacrifice creatures you control',
)


def has_offering(card: CardInfo) -> bool:
    """Return True when the card has offering."""
    if 'Artifact' not in card.type_line:
        return False
    return has_registered_keyword(card.oracle_text, 'Offering') or bool(
        _OFFERING_RE.search(card.oracle_text or '')
    )


def normalize_offering_cast(card: CardInfo, cast_for_offering: bool) -> bool:
    """Return whether this cast uses offering."""
    return cast_for_offering and has_offering(card)


def offering_mana_reduction(card: CardInfo, cast_for_offering: bool) -> int:
    """Return generic mana saved when offering is paid with a sacrifice."""
    if not normalize_offering_cast(card, cast_for_offering):
        return 0
    return _OFFERING_REDUCTION


def normalize_offering_sacrifice_id(
    card: CardInfo,
    paid_offering: bool,
    sacrifice_ids: list[int],
) -> int | None:
    """Return the creature id sacrificed for offering, if any."""
    if not normalize_offering_cast(card, paid_offering):
        return None
    if not sacrifice_ids:
        return None
    return sacrifice_ids[0]


offering_sacrifice_error = make_creature_sacrifice_cast_error(
    CreatureSacrificeCastCheck(
        has_cost=has_offering,
        normalize_sacrifice_id=normalize_offering_sacrifice_id,
        cost=_OFFERING_COST,
    ),
)


def sacrifice_for_offering(
    zones: ZoneManager,
    game: GameState,
    sacrifice_id: int,
) -> Permanent:
    """Sacrifice a creature to pay offering."""
    return sacrifice_creature_for_cast_cost(zones, game, sacrifice_id, 'offering')
