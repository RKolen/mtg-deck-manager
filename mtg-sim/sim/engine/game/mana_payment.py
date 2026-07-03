"""Pay spell costs using the mana pool and tapped lands (Phase H)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords.other.affinity import affinity_reduction
from engine.cards.land_mana import parse_produced_mana_from_oracle
from engine.core.game_object import Permanent
from engine.core.mana import ManaCost, ManaPool

if TYPE_CHECKING:
    from engine.core.game_state import GameState
    from engine.core.zones import ZoneManager

_COLOR_PRIORITY = 'WUBRG'


def land_produces_colors(perm: Permanent) -> list[str]:
    """Return mana colors a land permanent can add when tapped."""
    if perm.card_info is not None and perm.card_info.produced_mana:
        return list(perm.card_info.produced_mana)
    if perm.card_info is not None:
        parsed = parse_produced_mana_from_oracle(
            perm.card_info.oracle_text,
            type_line=perm.card_info.type_line,
        )
        if parsed:
            return parsed
    return ['C']


def effective_cast_cost(
    card: CardInfo,
    zones: ZoneManager | None,
    controller_idx: int,
    land_slots: int,
) -> ManaCost:
    """Build the ManaCost to pay, using colored pips when the slot count matches MV."""
    parsed = ManaCost.parse(card.mana_cost or '')
    if zones is not None:
        parsed.generic = max(0, parsed.generic - affinity_reduction(card, zones, controller_idx))
    if land_slots == int(card.cmc) and card.mana_cost:
        return parsed
    return ManaCost(generic=land_slots)


def _pick_land_color(cost: ManaCost, pool: ManaPool, options: list[str]) -> str:
    if len(options) == 1:
        return options[0]
    for color in _COLOR_PRIORITY:
        if color not in options:
            continue
        needed = cost.pips.get(color, 0) - pool.of_color(color)
        if needed > 0:
            return color
    return options[0]


def _simulate_pay(cost: ManaCost, pool: ManaPool, lands: list[Permanent]) -> bool:
    working = ManaPool(pool=list(pool.pool))
    for land in lands:
        if working.can_pay(cost):
            return True
        color = _pick_land_color(cost, working, land_produces_colors(land))
        working.add_color(color)
    return working.can_pay(cost)


def can_pay_cast_mana(
    zones: ZoneManager,
    controller_idx: int,
    card: CardInfo,
    land_slots: int,
) -> bool:
    """Return True when untapped lands can pay the spell's effective cost."""
    cost = effective_cast_cost(card, zones, controller_idx, land_slots)
    pool = ManaPool()
    return _simulate_pay(cost, pool, zones.untapped_lands_of(controller_idx))


def _commit_pay(cost: ManaCost, pool: ManaPool, lands: list[Permanent]) -> bool:
    tapped: list[Permanent] = []
    for land in lands:
        if pool.can_pay(cost):
            pool.pay(cost)
            for permanent in tapped:
                permanent.tapped = True
            return True
        color = _pick_land_color(cost, pool, land_produces_colors(land))
        pool.add_color(color)
        tapped.append(land)
    if pool.can_pay(cost):
        pool.pay(cost)
        for permanent in tapped:
            permanent.tapped = True
        return True
    return False


def pay_cast_mana(
    game: GameState,
    player_idx: int,
    card: CardInfo,
    land_slots: int,
) -> bool:
    """Tap lands and spend the mana pool to pay for a spell."""
    cost = effective_cast_cost(card, game.zones, player_idx, land_slots)
    pool = game.players[player_idx].mana_pool
    if pool.can_pay(cost):
        pool.pay(cost)
        return True
    lands = game.zones.untapped_lands_of(player_idx)
    if _commit_pay(cost, pool, lands):
        return True
    if land_slots != int(card.cmc) or not card.mana_cost:
        generic_only = ManaCost(generic=land_slots)
        pool.empty()
        return _commit_pay(generic_only, pool, lands)
    return False
