"""Shared helpers for the interactive game package."""

from __future__ import annotations

from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.activated.bloodrush import (
    bloodrush_mana_needed,
    can_bloodrush,
    has_bloodrush,
)
from engine.abilities.activated.card_keyword_abilities import can_channel, can_cycle
from engine.abilities.keywords.casting.foretell import can_foretell_setup, has_foretell
from engine.abilities.keywords.casting.madness import (
    can_cast_via_madness,
    has_madness,
    madness_mana_needed,
)
from engine.abilities.keywords.casting.plot import can_plot_setup, is_plottable_sorcery
from engine.abilities.keywords.casting.suspend import can_suspend, suspend_mana_needed
from engine.abilities.keywords import has_flash
from engine.abilities.keywords.casting.convoke import has_convoke
from engine.abilities.keywords.casting.delve import has_delve
from engine.abilities.keywords.casting.emerge import has_emerge
from engine.abilities.keywords.casting.evoke import evoke_mana_needed, has_evoke
from engine.abilities.keywords.casting.improvise import has_improvise
from engine.abilities.keywords.other.ninjutsu import (
    can_ninjutsu,
    has_ninjutsu,
    ninjutsu_mana_needed,
)
from engine.cards.oracle_parse import is_affordable, spell_category
from engine.core.game_object import (
    ActivatedAbilityOnStack,
    CardObject,
    Permanent,
    TriggeredAbilityOnStack,
)
from engine.core.game_object import Target
from engine.core.game_state import GameState
from engine.core.zones import ZoneManager
from engine.game.cast_context import (
    CastAnnounceOptions,
    CastModifierIds,
    SpellCastContext,
    spell_on_stack_from_context,
)

__all__ = [
    "CastAnnounceOptions",
    "CastModifierIds",
    "SpellCastContext",
    "card_names",
    "card_to_client",
    "HandCastContext",
    "has_instant_timing",
    "is_land",
    "last_creature",
    "payment_requirements",
    "perm_names",
    "require_card_info",
    "resolve_ability_effect",
    "spell_on_stack_from_context",
    "target_player",
    "target_uid",
    "targets_from_request",
]


@dataclass(frozen=True)
class HandCastContext:
    """Timing and affinity context for serialising a hand card."""

    phase: str = 'main1'
    stack_is_empty: bool = True
    zones: ZoneManager | None = None
    controller_idx: int = 0


def expand_deck(cards: list[CardInfo], player_idx: int) -> list[CardObject]:
    """Expand CardInfo quantities into CardObjects."""
    result: list[CardObject] = []
    for card in cards:
        if card.sideboard:
            continue
        for _ in range(card.quantity):
            result.append(CardObject(
                controller_idx=player_idx,
                owner_idx=player_idx,
                card_info=card,
            ))
    return result


def _hand_alt_activation_flags(
    card: CardInfo,
    phase: str,
    stack_is_empty: bool,
    available_mana: int,
) -> dict[str, bool]:
    """Return per-card suspend/foretell/plot/madness UI flags for hand cards."""
    suspend_ok = can_suspend(card, phase, stack_is_empty)
    foretell_ok = has_foretell(card) and can_foretell_setup(phase, stack_is_empty)
    plot_ok = is_plottable_sorcery(card) and can_plot_setup(phase, stack_is_empty)
    madness_ok = has_madness(card) and can_cast_via_madness(card, phase, stack_is_empty)
    return {
        "canSuspend": suspend_ok,
        "suspendAffordable": suspend_ok and available_mana >= suspend_mana_needed(card)[0],
        "canForetell": foretell_ok,
        "canPlot": plot_ok,
        "hasMadness": madness_ok,
        "madnessAffordable": madness_ok and available_mana >= madness_mana_needed(card)[0],
    }


def card_to_client(
    idx: int,
    card: CardInfo,
    available_mana: int,
    context: HandCastContext | None = None,
) -> dict:
    """Serialise one hand card using the existing client shape."""
    ctx = context or HandCastContext()
    zones = ctx.zones
    controller_idx = ctx.controller_idx
    affordable = is_affordable(
        card,
        available_mana,
        zones=zones,
        controller_idx=controller_idx,
    )
    has_evoke_kw = has_evoke(card)
    evoke_mana = evoke_mana_needed(card)[0] if has_evoke_kw else 0
    bloodrush = has_bloodrush(card)
    bloodrush_ok = bloodrush and can_bloodrush(card, ctx.phase, ctx.stack_is_empty)
    bloodrush_mana = bloodrush_mana_needed(card) if bloodrush else 0
    alt_flags = _hand_alt_activation_flags(
        card,
        ctx.phase,
        ctx.stack_is_empty,
        available_mana,
    )
    return {
        "idx": idx,
        "name": card.name,
        "cmc": card.cmc,
        "type": card.short_type(),
        "power": card.numeric_power,
        "toughness": card.numeric_toughness,
        "oracle": card.oracle_text or "",
        "category": spell_category(card),
        "isLand": card.is_land,
        "isCreature": card.is_creature,
        "affordable": affordable,
        "hasEvoke": has_evoke_kw,
        "evokeAffordable": has_evoke_kw and available_mana >= evoke_mana,
        "hasConvoke": has_convoke(card),
        "hasDelve": has_delve(card),
        "hasImprovise": has_improvise(card),
        "hasEmerge": has_emerge(card),
        "canBloodrush": bloodrush_ok,
        "bloodrushAffordable": bloodrush_ok and available_mana >= bloodrush_mana,
        "canCycle": can_cycle(card, ctx.phase, ctx.stack_is_empty),
        "canChannel": can_channel(card, ctx.phase, ctx.stack_is_empty),
        "canNinjutsu": can_ninjutsu(card, ctx.phase, ctx.stack_is_empty),
        "ninjutsuAffordable": (
            can_ninjutsu(card, ctx.phase, ctx.stack_is_empty)
            and available_mana >= ninjutsu_mana_needed(card)
        )
        if has_ninjutsu(card)
        else False,
        **alt_flags,
    }


def payment_requirements(card: CardInfo) -> tuple[int, int]:
    """Return mana and life needed for simplified payment."""
    phyrexian_pips = (card.mana_cost or "").upper().count("/P")
    total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
    return max(0, total_cmc - phyrexian_pips), phyrexian_pips * 2


def require_card_info(card: CardObject) -> CardInfo:
    """Return card_info for a real card object."""
    assert card.card_info is not None
    return card.card_info


def is_land(card: CardObject) -> bool:
    """Return True when the card object is a land."""
    return require_card_info(card).is_land


def can_cast_now(card: CardInfo, phase: str, stack_is_empty: bool) -> bool:
    """Return whether the player can cast a card in the current Phase B window."""
    if card.is_land:
        return False
    if has_instant_timing(card):
        return phase in ("main1", "main2", "attack", "declare_blockers")
    return phase in ("main1", "main2") and stack_is_empty


def has_instant_timing(card: CardInfo) -> bool:
    """Return whether a spell can be cast at instant speed."""
    return has_flash(card)


def targets_from_request(
    target_uid_str: str | None,
    target_player_idx: int | None,
) -> list[Target]:
    """Convert the legacy action payload target fields to stack targets."""
    targets: list[Target] = []
    if target_uid_str is not None:
        try:
            targets.append(Target(obj_id=int(target_uid_str)))
        except ValueError:
            return targets
    if target_player_idx is not None:
        targets.append(Target(player_idx=target_player_idx))
    return targets


def target_uid(targets: list[Target]) -> str | None:
    """Return the first permanent target as a legacy uid string."""
    target = next((t for t in targets if t.obj_id is not None), None)
    return str(target.obj_id) if target is not None else None


def target_player(targets: list[Target]) -> int | None:
    """Return the first player target index."""
    target = next((t for t in targets if t.player_idx is not None), None)
    return target.player_idx if target is not None else None


def resolve_ability_effect(
    obj: TriggeredAbilityOnStack | ActivatedAbilityOnStack,
    game: GameState,
) -> str:
    """Apply an ability effect if one is attached to the stack object."""
    if obj.effect is None:
        return "Resolved ability"
    detail = obj.effect.resolve(game, obj)
    return detail or "Resolved ability"


def last_creature(permanents: list[Permanent]) -> Permanent | None:
    """Return the last creature on a list of permanents."""
    creatures = [p for p in permanents if "Creature" in p.type_line]
    return creatures[-1] if creatures else None


def card_names(cards: list[CardObject]) -> str:
    """Format card names for log messages."""
    return ", ".join(require_card_info(c).name for c in cards)


def perm_names(permanents: list[Permanent]) -> str:
    """Format permanent names for log messages."""
    return ", ".join(p.name for p in permanents)
