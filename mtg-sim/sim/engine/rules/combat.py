"""Combat helpers for the interactive game loop."""

from __future__ import annotations

from dataclasses import dataclass

from engine.core.game_object import Permanent
from engine.core.game_state import GameState


@dataclass
class CombatDamageResult:
    """Summary of one combat damage assignment."""

    attackers: list[Permanent]
    damage_to_player: int = 0
    blocked_attackers: int = 0


@dataclass(frozen=True)
class _CombatContext:
    """Shared data for a combat damage assignment."""

    game: GameState
    attacking_player_idx: int
    defending_player_idx: int
    result: CombatDamageResult


def can_attack(perm: Permanent) -> bool:
    """Return whether a permanent can attack under current combat rules."""
    return (
        _is_creature(perm)
        and not perm.tapped
        and not perm.sick
        and not _has_keyword(perm, "defender")
    )


def can_block(perm: Permanent) -> bool:
    """Return whether a permanent can be declared as a blocker."""
    return _is_creature(perm) and not perm.tapped


def legal_blocker(blocker: Permanent, attacker: Permanent, game: GameState) -> bool:
    """Return whether blocker can block attacker."""
    del game
    if not can_block(blocker):
        return False
    if _has_keyword(attacker, "flying"):
        return _has_keyword(blocker, "flying") or _has_keyword(blocker, "reach")
    return True


def power(perm: Permanent) -> int:
    """Return current combat power using printed P/T plus +/- counters."""
    base = perm.card_info.numeric_power if perm.card_info is not None else 0
    return base + perm.counters.get("+1/+1", 0) - perm.counters.get("-1/-1", 0)


def eligible_attackers(permanents: list[Permanent]) -> list[Permanent]:
    """Return permanents from the list that can legally attack."""
    return [perm for perm in permanents if can_attack(perm)]


def tap_attackers(attackers: list[Permanent]) -> None:
    """Tap attackers as part of declaring them unless they have vigilance."""
    for attacker in attackers:
        if not _has_keyword(attacker, "vigilance"):
            attacker.tapped = True


def resolve_combat_damage(
    game: GameState,
    attacking_player_idx: int,
    defending_player_idx: int,
    attacker_ids: list[str],
    blocker_assignments: dict[str, str],
) -> CombatDamageResult:
    """Assign simplified combat damage for one attacking player."""
    attackers = _selected_attackers(game, attacking_player_idx, attacker_ids)
    result = CombatDamageResult(attackers=attackers)
    context = _CombatContext(game, attacking_player_idx, defending_player_idx, result)
    tap_attackers(attackers)

    for attacker in attackers:
        blockers = _blockers_for(game, defending_player_idx, attacker, blocker_assignments)
        is_blocked = _has_enough_blockers(attacker, blockers)
        _resolve_first_strike_damage(context, attacker, blockers, is_blocked)
        _resolve_regular_combat_damage(context, attacker, blockers, is_blocked)

    if result.damage_to_player:
        game.players[defending_player_idx].life -= result.damage_to_player
    game.check_sbas()
    return result


def _resolve_first_strike_damage(
    context: _CombatContext,
    attacker: Permanent,
    blockers: list[Permanent],
    is_blocked: bool,
) -> None:
    """Resolve first-strike damage, then SBAs before regular damage."""
    first_strikers = [
        perm for perm in [attacker, *blockers] if _has_early_strike(perm)
    ]
    if not first_strikers:
        return
    _assign_combat_damage(context, attacker, blockers, is_blocked, first_strike_step=True)
    context.game.check_sbas()


def _resolve_regular_combat_damage(
    context: _CombatContext,
    attacker: Permanent,
    blockers: list[Permanent],
    is_blocked: bool,
) -> None:
    """Resolve regular combat damage from surviving non-first-strikers."""
    if attacker not in context.game.zones.battlefield:
        return
    live_blockers = [
        blocker for blocker in blockers if blocker in context.game.zones.battlefield
    ]
    _assign_combat_damage(
        context,
        attacker,
        live_blockers,
        is_blocked,
        first_strike_step=False,
    )


def _assign_combat_damage(
    context: _CombatContext,
    attacker: Permanent,
    blockers: list[Permanent],
    is_blocked: bool,
    first_strike_step: bool,
) -> None:
    attacker_deals = _deals_in_step(attacker, first_strike_step)
    if not is_blocked:
        if attacker_deals:
            damage = power(attacker)
            context.result.damage_to_player += damage
            context.game.fire_combat_damage_triggers(
                attacker,
                damage,
                damaged_player_idx=context.defending_player_idx,
            )
            _apply_lifelink(
                context.game,
                context.attacking_player_idx,
                attacker,
                damage,
            )
        return
    if not first_strike_step:
        context.result.blocked_attackers += 1
    if attacker_deals:
        damage = power(attacker)
        player_damage = _assign_attacker_damage(context, attacker, blockers, damage)
        context.result.damage_to_player += player_damage
        context.game.fire_combat_damage_triggers(
            attacker,
            player_damage,
            damaged_player_idx=context.defending_player_idx,
        )
        _apply_lifelink(context.game, context.attacking_player_idx, attacker, damage)
    for blocker in blockers:
        if _deals_in_step(blocker, first_strike_step):
            damage = power(blocker)
            _mark_combat_damage(attacker, blocker, damage)
            context.game.fire_combat_damage_triggers(
                blocker,
                damage,
                damaged_permanent=attacker,
            )
            _apply_lifelink(context.game, context.defending_player_idx, blocker, damage)


def _selected_attackers(
    game: GameState,
    attacking_player_idx: int,
    attacker_ids: list[str],
) -> list[Permanent]:
    selected = set(attacker_ids)
    return [
        perm for perm in game.zones.permanents_of(attacking_player_idx)
        if str(perm.obj_id) in selected
    ]


def _blockers_for(
    game: GameState,
    defending_player_idx: int,
    attacker: Permanent,
    blocker_assignments: dict[str, str],
) -> list[Permanent]:
    blockers = []
    for blocker_uid, attacker_uid in blocker_assignments.items():
        if attacker_uid != str(attacker.obj_id):
            continue
        blocker = _find_permanent(game, blocker_uid)
        if (
            blocker is not None
            and blocker.controller_idx == defending_player_idx
            and legal_blocker(blocker, attacker, game)
        ):
            blockers.append(blocker)
    return blockers


def _has_enough_blockers(attacker: Permanent, blockers: list[Permanent]) -> bool:
    if _has_keyword(attacker, "menace"):
        return len(blockers) >= 2
    return bool(blockers)


def _deals_in_step(perm: Permanent, first_strike_step: bool) -> bool:
    if first_strike_step:
        return _has_early_strike(perm)
    return _has_double_strike(perm) or not _has_early_strike(perm)


def _has_early_strike(perm: Permanent) -> bool:
    return _has_keyword(perm, "first strike") or _has_double_strike(perm)


def _has_double_strike(perm: Permanent) -> bool:
    return _has_keyword(perm, "double strike")


def _apply_lifelink(
    game: GameState,
    controller_idx: int,
    source: Permanent,
    damage_dealt: int,
) -> None:
    if damage_dealt > 0 and _has_keyword(source, "lifelink"):
        game.gain_life(controller_idx, damage_dealt, source.obj_id)


def _assign_attacker_damage(
    context: _CombatContext,
    attacker: Permanent,
    blockers: list[Permanent],
    attacker_power: int,
) -> int:
    """Assign attacker damage to blockers, returning trample damage to player."""
    remaining = attacker_power
    for blocker in blockers:
        assigned = min(remaining, _lethal_damage(attacker, blocker))
        _mark_combat_damage(blocker, attacker, assigned)
        context.game.fire_combat_damage_triggers(
            attacker,
            assigned,
            damaged_permanent=blocker,
        )
        remaining -= assigned
        if remaining <= 0:
            return 0
    if _has_keyword(attacker, "trample"):
        return remaining
    return 0


def _lethal_damage(source: Permanent, receiver: Permanent) -> int:
    if _has_keyword(source, "deathtouch"):
        return 1
    return max(0, _toughness(receiver) - receiver.damage_marked)


def _mark_combat_damage(receiver: Permanent, source: Permanent, damage: int) -> None:
    """Mark combat damage, treating deathtouch damage as lethal."""
    if damage <= 0:
        return
    receiver.damage_marked += damage
    if _has_keyword(source, "deathtouch"):
        receiver.damage_marked = max(receiver.damage_marked, _toughness(receiver))


def _toughness(perm: Permanent) -> int:
    if perm.card_info is None:
        return 0
    return (
        perm.card_info.numeric_toughness
        + perm.counters.get("+1/+1", 0)
        - perm.counters.get("-1/-1", 0)
    )


def _find_permanent(game: GameState, uid: str) -> Permanent | None:
    try:
        return game.zones.find_permanent(int(uid))
    except ValueError:
        return None


def _is_creature(perm: Permanent) -> bool:
    return "Creature" in perm.type_line


def _has_keyword(perm: Permanent, keyword: str) -> bool:
    return keyword.lower() in perm.oracle_text.lower()
