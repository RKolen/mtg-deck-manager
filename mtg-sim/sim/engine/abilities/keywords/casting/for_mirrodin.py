"""For Mirrodin!: sacrifice a creature when you cast this Equipment."""

from __future__ import annotations

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

_FOR_MIRRODIN_COST = CreatureSacrificeCost(
    label='For Mirrodin!',
    missing_message='For Mirrodin! requires sacrificing a creature',
    not_found_fmt='For Mirrodin! sacrifice {sacrifice_id} not found',
    wrong_controller_message='For Mirrodin! may only sacrifice creatures you control',
)


def has_for_mirrodin(card: CardInfo) -> bool:
    """Return True when the equipment has For Mirrodin!."""
    if 'Equipment' not in card.type_line:
        return False
    return has_registered_keyword(card.oracle_text, 'For Mirrodin!')


def normalize_paid_for_mirrodin(card: CardInfo, paid: bool) -> bool:
    """Return whether this cast pays For Mirrodin!."""
    return paid and has_for_mirrodin(card)


def normalize_for_mirrodin_sacrifice_id(
    card: CardInfo,
    paid: bool,
    sacrifice_ids: list[int],
) -> int | None:
    """Return the creature id sacrificed for For Mirrodin!, if any."""
    if not normalize_paid_for_mirrodin(card, paid):
        return None
    if not sacrifice_ids:
        return None
    return sacrifice_ids[0]


for_mirrodin_sacrifice_error = make_creature_sacrifice_cast_error(
    CreatureSacrificeCastCheck(
        has_cost=has_for_mirrodin,
        normalize_sacrifice_id=normalize_for_mirrodin_sacrifice_id,
        cost=_FOR_MIRRODIN_COST,
    ),
)


def sacrifice_for_for_mirrodin(
    zones: ZoneManager,
    game: GameState,
    sacrifice_id: int,
) -> Permanent:
    """Sacrifice a creature to pay For Mirrodin!."""
    return sacrifice_creature_for_cast_cost(zones, game, sacrifice_id, 'for_mirrodin')
