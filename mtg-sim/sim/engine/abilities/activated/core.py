"""Core activated-ability parsing, mana abilities, and equip (CR 605, CR 301)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from engine.abilities.keywords.ability_words.effects import AbilityWordEffect
from engine.core.game_object import ActivatedAbilityOnStack, Permanent, Target
from engine.core.mana import ManaCost, mana_of

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_TAP_COST = "{T}"
_EQUIP_RE = re.compile(r"equip\s+(\{[^}]+\})", re.IGNORECASE)


class ActivationSpeed(Enum):
    """When an activated ability may be started."""

    INSTANT = "instant"
    SORCERY = "sorcery"


@dataclass(frozen=True)
class ActivatedAbilitySpec:
    """One activated ability parsed from oracle text."""

    cost_text: str
    effect_text: str
    mana_ability: bool = False
    equip: bool = False


@dataclass(frozen=True)
class ActivationResult:
    """Outcome of trying to activate an ability."""

    ok: bool
    detail: str = ""
    used_stack: bool = False


def parse_activated_abilities(oracle_text: str) -> list[ActivatedAbilitySpec]:
    """Parse activated abilities from oracle text lines containing ':'."""
    specs: list[ActivatedAbilitySpec] = []
    for raw_line in oracle_text.split("\n"):
        line = raw_line.strip()
        if ":" not in line:
            continue
        cost_text, effect_text = line.split(":", maxsplit=1)
        cost_text = cost_text.strip()
        effect_text = effect_text.strip()
        if not cost_text or not effect_text:
            continue
        equip = bool(_EQUIP_RE.search(cost_text))
        specs.append(ActivatedAbilitySpec(
            cost_text=cost_text,
            effect_text=effect_text,
            mana_ability=is_mana_ability_text(effect_text),
            equip=equip,
        ))
    return specs


def is_mana_ability_text(effect_text: str) -> bool:
    """Return True when effect text describes adding mana (CR 605.1a)."""
    lowered = effect_text.lower()
    return "add " in lowered and "loyalty" not in lowered


def requires_tap(cost_text: str) -> bool:
    """Return True when the cost includes a tap symbol."""
    return _TAP_COST in cost_text


def activation_mana_value(cost_text: str) -> int:
    """Return simplified generic mana (lands to tap) for an activation cost."""
    stripped = cost_text.replace(_TAP_COST, "")
    equip_match = _EQUIP_RE.search(stripped)
    if equip_match is not None:
        stripped = stripped[:equip_match.start()] + stripped[equip_match.end():]
    stripped = stripped.strip()
    if not stripped:
        return 0
    return ManaCost.parse(stripped).mana_value


def equip_cost(cost_text: str) -> ManaCost | None:
    """Return parsed equip mana cost, or None when not an equip ability."""
    match = _EQUIP_RE.search(cost_text)
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def can_activate(
    perm: Permanent,
    spec: ActivatedAbilitySpec,
    game: GameState,
    controller_idx: int,
    speed: ActivationSpeed,
) -> bool:
    """Return True when the permanent's ability can be activated now."""
    if perm.controller_idx != controller_idx:
        return False
    if perm.tapped and requires_tap(spec.cost_text):
        return False
    if spec.equip and speed != ActivationSpeed.SORCERY:
        return False
    if spec.equip and not game.stack.is_empty:
        return False
    if spec.mana_ability:
        return True
    return speed == ActivationSpeed.INSTANT or (
        speed == ActivationSpeed.SORCERY and game.stack.is_empty
    )


def activate_mana_ability(game: GameState, perm: Permanent, spec: ActivatedAbilitySpec) -> str:
    """Resolve a mana ability immediately: tap (if required) and add mana."""
    if not spec.mana_ability:
        return ""
    if requires_tap(spec.cost_text):
        perm.tapped = True
    colors = _mana_from_spec(perm, spec.effect_text)
    pool = game.players[perm.controller_idx].mana_pool
    for color in colors:
        pool.add(mana_of(color))
    joined = "".join(colors) or "C"
    return f"{perm.name} added {{{joined}}}"


def activate_on_stack(
    game: GameState,
    perm: Permanent,
    spec: ActivatedAbilitySpec,
    ability_idx: int,
    targets: list[Target] | None = None,
    *,
    mana_paid: bool = False,
) -> ActivationResult:
    """Pay costs and put a non-mana activated ability on the stack."""
    if spec.mana_ability:
        detail = activate_mana_ability(game, perm, spec)
        return ActivationResult(ok=bool(detail), detail=detail, used_stack=False)
    if spec.equip:
        return ActivationResult(ok=False, detail="Use equip activation with a host")
    if requires_tap(spec.cost_text) and perm.tapped:
        return ActivationResult(ok=False, detail="Already tapped")
    mana_needed = activation_mana_value(spec.cost_text)
    if mana_needed > 0 and not mana_paid:
        return ActivationResult(ok=False, detail=f"Need {mana_needed} mana")
    if requires_tap(spec.cost_text):
        perm.tapped = True
    effect = AbilityWordEffect(spec.effect_text) if spec.effect_text else None
    game.stack.push(ActivatedAbilityOnStack(
        controller_idx=perm.controller_idx,
        owner_idx=perm.owner_idx,
        source_permanent_id=perm.obj_id,
        ability_idx=ability_idx,
        effect=effect,
        targets=targets or [],
    ))
    return ActivationResult(ok=True, detail=f"{perm.name} activated", used_stack=True)


def activatable_ability_indices(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    speed: ActivationSpeed,
) -> list[int]:
    """Return ability indices that can be activated at the given speed."""
    indices: list[int] = []
    for idx, spec in enumerate(parse_activated_abilities(perm.oracle_text)):
        if can_activate(perm, spec, game, controller_idx, speed):
            indices.append(idx)
    return indices


def activate_equip(
    game: GameState,
    equipment: Permanent,
    host: Permanent,
    spec: ActivatedAbilitySpec,
) -> ActivationResult:
    """Activate an equip ability at sorcery speed and attach equipment to host."""
    if not spec.equip:
        return ActivationResult(ok=False, detail="Not an equip ability")
    if not can_activate(equipment, spec, game, equipment.controller_idx, ActivationSpeed.SORCERY):
        return ActivationResult(ok=False, detail="Cannot equip now")
    if "Creature" not in host.type_line:
        return ActivationResult(ok=False, detail="Host must be a creature")
    cost = equip_cost(spec.cost_text)
    if cost is not None and not game.players[equipment.controller_idx].mana_pool.can_pay(cost):
        return ActivationResult(ok=False, detail="Cannot pay equip cost")
    if cost is not None:
        game.players[equipment.controller_idx].mana_pool.pay(cost)
    if requires_tap(spec.cost_text):
        equipment.tapped = True
    equipment.attached_to = host.obj_id
    return ActivationResult(ok=True, detail=f"{equipment.name} attached to {host.name}")


def _mana_from_spec(perm: Permanent, effect_text: str) -> list[str]:
    """Return mana colors produced by a mana ability."""
    if perm.card_info is not None and perm.card_info.produced_mana:
        return list(perm.card_info.produced_mana)
    match = re.search(r"add (\{[WRUBGC]+\})", effect_text, re.IGNORECASE)
    if match:
        parsed = ManaCost.parse(match.group(1))
        return [color for color, count in parsed.pips.items() for _ in range(count)]
    if "any color" in effect_text.lower():
        return ["C"]
    return ["C"]
