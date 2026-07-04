"""Core activated-ability parsing, mana abilities, and equip (CR 605, CR 301)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities.keywords.ability_words.effects import AbilityWordEffect
from engine.core.game_object import ActivatedAbilityOnStack, Permanent, Target
from engine.core.mana import ManaCost, mana_of
from engine.rules.mana_payment import pay_mana_cost

if TYPE_CHECKING:
    from engine.core.game_state import GameState

_TAP_COST = "{T}"
_EQUIP_RE = re.compile(r"equip\s+(\{[^}]+\})", re.IGNORECASE)
_LOYALTY_COST_RE = re.compile(r"^([+−-])\s*(\d+)")


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
        if _EQUIP_RE.search(line) and ":" not in line:
            specs.append(ActivatedAbilitySpec(
                cost_text=line,
                effect_text="Attach this Equipment to target creature",
                equip=True,
            ))
            continue
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
    return activation_mana_cost(cost_text).mana_value


def activation_mana_cost(cost_text: str) -> ManaCost:
    """Return the mana portion of an activation cost (excluding tap and equip)."""
    stripped = cost_text.replace(_TAP_COST, "")
    equip_only = equip_cost(stripped)
    if equip_only is not None and _EQUIP_RE.match(stripped.strip()):
        return equip_only
    equip_match = _EQUIP_RE.search(stripped)
    if equip_match is not None:
        stripped = stripped[:equip_match.start()] + stripped[equip_match.end():]
    stripped = _strip_loyalty_prefix(stripped.strip())
    if not stripped:
        return ManaCost()
    return ManaCost.parse(stripped)


def loyalty_cost_change(cost_text: str) -> int | None:
    """Return loyalty added or removed by a planeswalker ability cost."""
    match = _LOYALTY_COST_RE.match(cost_text.strip())
    if match is None:
        return None
    sign = -1 if match.group(1) in '-−' else 1
    return sign * int(match.group(2))


def can_pay_loyalty(perm: Permanent, delta: int) -> bool:
    """Return True when the permanent can pay a loyalty cost."""
    if delta >= 0:
        return True
    return perm.counters.get('loyalty', 0) + delta >= 0


def _strip_loyalty_prefix(cost_text: str) -> str:
    """Remove a leading loyalty cost from an activation cost string."""
    return _LOYALTY_COST_RE.sub('', cost_text, count=1).strip(' ,')


def equip_cost(cost_text: str) -> ManaCost | None:
    """Return parsed equip mana cost, or None when not an equip ability."""
    match = _EQUIP_RE.search(cost_text)
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def has_equip(card: CardInfo) -> bool:
    """Return True when the card is equipment with an equip ability."""
    if 'Equipment' not in (card.type_line or ''):
        return False
    return any(spec.equip for spec in parse_activated_abilities(card.oracle_text or ''))


def has_equip_card(card: CardInfo) -> bool:
    """Return True when the card has equip."""
    return has_equip(card)


def equip_mana_needed(card: CardInfo) -> int:
    """Return generic mana to pay the first equip ability on this card."""
    for spec in parse_activated_abilities(card.oracle_text or ''):
        if spec.equip:
            return activation_mana_value(spec.cost_text)
    return 0


def has_mana_ability(card: CardInfo) -> bool:
    """Return True when the card has a mana activated ability."""
    return any(
        spec.mana_ability for spec in parse_activated_abilities(card.oracle_text or '')
    )


def has_mana_ability_card(card: CardInfo) -> bool:
    """Return True when the card has a mana ability."""
    return has_mana_ability(card)


def _activation_speed_ok(
    spec: ActivatedAbilitySpec,
    game: GameState,
    speed: ActivationSpeed,
) -> bool:
    """Return True when stack/phase rules allow activation at this speed."""
    if spec.mana_ability:
        return True
    if speed == ActivationSpeed.INSTANT:
        return True
    return speed == ActivationSpeed.SORCERY and game.stack.is_empty


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
    if spec.equip and (
        speed != ActivationSpeed.SORCERY or not game.stack.is_empty
    ):
        return False
    loyalty = loyalty_cost_change(spec.cost_text)
    if loyalty is not None and not can_pay_loyalty(perm, loyalty):
        return False
    return _activation_speed_ok(spec, game, speed)


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


@dataclass(frozen=True)
class _ActivationCall:
    ability_idx: int
    targets: list[Target] = field(default_factory=list)
    mana_paid: bool = False


def _pay_loyalty_activation_cost(
    perm: Permanent,
    spec: ActivatedAbilitySpec,
    call: _ActivationCall,
) -> ActivationResult | None:
    """Pay loyalty cost or return an error result; None when no loyalty cost."""
    loyalty = loyalty_cost_change(spec.cost_text)
    if loyalty is None:
        return None
    if not call.mana_paid:
        return ActivationResult(ok=False, detail="Need loyalty payment")
    if not can_pay_loyalty(perm, loyalty):
        return ActivationResult(ok=False, detail="Not enough loyalty")
    perm.counters['loyalty'] = perm.counters.get('loyalty', 0) + loyalty
    return None


def activate_on_stack(
    game: GameState,
    perm: Permanent,
    spec: ActivatedAbilitySpec,
    call: _ActivationCall,
) -> ActivationResult:
    """Pay costs and put a non-mana activated ability on the stack."""
    if spec.mana_ability:
        detail = activate_mana_ability(game, perm, spec)
        return ActivationResult(ok=bool(detail), detail=detail, used_stack=False)
    if spec.equip or (requires_tap(spec.cost_text) and perm.tapped):
        detail = (
            "Use equip activation with a host"
            if spec.equip
            else "Already tapped"
        )
        return ActivationResult(ok=False, detail=detail)
    loyalty_err = _pay_loyalty_activation_cost(perm, spec, call)
    if loyalty_err is not None:
        return loyalty_err
    mana_needed = activation_mana_value(spec.cost_text)
    if mana_needed > 0 and not call.mana_paid:
        return ActivationResult(ok=False, detail=f"Need {mana_needed} mana")
    if requires_tap(spec.cost_text):
        perm.tapped = True
    effect = AbilityWordEffect(spec.effect_text) if spec.effect_text else None
    game.stack.push(ActivatedAbilityOnStack(
        controller_idx=perm.controller_idx,
        owner_idx=perm.owner_idx,
        source_permanent_id=perm.obj_id,
        ability_idx=call.ability_idx,
        effect=effect,
        targets=call.targets,
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
    if cost is not None and cost.mana_value > 0:
        if not pay_mana_cost(game, equipment.controller_idx, cost):
            return ActivationResult(ok=False, detail="Cannot pay equip cost")
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
