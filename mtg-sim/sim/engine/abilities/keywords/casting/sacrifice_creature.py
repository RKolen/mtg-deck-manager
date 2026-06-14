"""Shared creature-sacrifice validation for cast costs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from deck_registry import CardInfo
from engine.core.game_object import Permanent
from engine.core.game_state import GameState
from engine.core.zones import Zone, ZoneManager


@dataclass(frozen=True)
class CreatureSacrificeCost:
    """Labels and messages for a creature sacrifice cast cost."""

    label: str
    missing_message: str
    not_found_fmt: str
    wrong_controller_message: str


@dataclass(frozen=True)
class CreatureSacrificeCastCheck:
    """Callbacks and messages for validating a creature sacrifice cast."""

    has_cost: Callable[[CardInfo], bool]
    normalize_sacrifice_id: Callable[[CardInfo, bool, list[int]], int | None]
    cost: CreatureSacrificeCost


@dataclass(frozen=True)
class CastSacrificeContext:
    """Runtime context for validating a creature sacrifice on cast."""

    zones: ZoneManager
    player_idx: int
    card: CardInfo
    paid: bool
    sacrifice_ids: list[int]
    check: CreatureSacrificeCastCheck


def creature_sacrifice_target_error(
    zones: ZoneManager,
    player_idx: int,
    sacrifice_id: int | None,
    cost: CreatureSacrificeCost,
) -> str | None:
    """Return an error when a creature sacrifice target is illegal."""
    if sacrifice_id is None:
        return cost.missing_message
    perm = zones.find_permanent(sacrifice_id)
    if perm is None:
        return cost.not_found_fmt.format(sacrifice_id=sacrifice_id)
    if perm.controller_idx != player_idx:
        return cost.wrong_controller_message
    if 'Creature' not in perm.type_line:
        return f"{perm.name} is not a creature"
    return None


def optional_creature_sacrifice_cast_error(ctx: CastSacrificeContext) -> str | None:
    """Return an error when an optional creature sacrifice cost is illegal."""
    check = ctx.check
    cost = check.cost
    message: str | None = None
    if not ctx.paid:
        if ctx.sacrifice_ids and check.has_cost(ctx.card):
            message = f"{ctx.card.name} was not cast with {cost.label}"
    elif not check.has_cost(ctx.card):
        message = f"{ctx.card.name} does not have {cost.label}"
    else:
        sacrifice_id = check.normalize_sacrifice_id(ctx.card, True, ctx.sacrifice_ids)
        message = creature_sacrifice_target_error(
            ctx.zones,
            ctx.player_idx,
            sacrifice_id,
            cost,
        )
    return message


def make_creature_sacrifice_cast_error(
    check: CreatureSacrificeCastCheck,
) -> Callable[[ZoneManager, int, CardInfo, bool, list[int]], str | None]:
    """Build a cast-error checker for a creature sacrifice cost."""

    def check_error(
        zones: ZoneManager,
        player_idx: int,
        card: CardInfo,
        paid: bool,
        sacrifice_ids: list[int],
    ) -> str | None:
        return optional_creature_sacrifice_cast_error(CastSacrificeContext(
            zones=zones,
            player_idx=player_idx,
            card=card,
            paid=paid,
            sacrifice_ids=sacrifice_ids,
            check=check,
        ))

    return check_error


def sacrifice_creature_for_cast_cost(
    zones: ZoneManager,
    game: GameState,
    sacrifice_id: int,
    cause: str,
) -> Permanent:
    """Sacrifice a creature to pay a cast cost."""
    perm = zones.find_permanent(sacrifice_id)
    assert perm is not None
    zones.leave_battlefield(perm, Zone.GRAVEYARD, cause, game)
    return perm
