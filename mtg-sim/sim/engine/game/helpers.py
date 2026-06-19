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
from engine.abilities.keywords.casting.assist import has_assist
from engine.abilities.keywords.casting.bargain import has_bargain
from engine.abilities.keywords.casting.cleave import has_cleave
from engine.abilities.keywords.casting.conspire import (
    conspire_color_match,
    has_conspire,
)
from engine.abilities.keywords.casting.demonstrate import has_demonstrate
from engine.abilities.keywords.casting.fuse import has_fuse
from engine.abilities.keywords.casting.gift import has_gift
from engine.abilities.keywords.casting.awaken import has_awaken
from engine.abilities.keywords.casting.for_mirrodin import has_for_mirrodin
from engine.abilities.keywords.casting.impending import has_impending
from engine.abilities.keywords.casting.offering import has_offering
from engine.abilities.keywords.casting.escalate import has_escalate
from engine.abilities.keywords.other.forecast import can_forecast, has_forecast
from engine.abilities.keywords.casting.convoke import has_convoke
from engine.abilities.keywords.casting.delve import has_delve
from engine.abilities.keywords.casting.emerge import has_emerge
from engine.abilities.keywords.casting.evoke import evoke_mana_needed, has_evoke
from engine.abilities.keywords.casting.improvise import has_improvise
from engine.abilities.keywords.casting.blitz import has_blitz
from engine.abilities.keywords.casting.dash import has_dash
from engine.abilities.keywords.casting.embalm import has_embalm
from engine.abilities.keywords.casting.freerunning import has_freerunning
from engine.abilities.keywords.casting.sneak import has_sneak
from engine.abilities.keywords.casting.spectacle import has_spectacle, spectacle_available
from engine.abilities.keywords.casting.surge import has_surge, surge_available
from engine.abilities.keywords.other.disguise import has_disguise
from engine.abilities.keywords.other.morph import has_morph
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
    game: GameState | None = None


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
) -> dict[str, object]:
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
    payload: dict[str, object] = {
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
        "hasAssist": has_assist(card),
        "hasBargain": has_bargain(card),
        "hasEscalate": has_escalate(card),
        "hasCleave": has_cleave(card),
        "canForecast": can_forecast(card, ctx.phase, ctx.stack_is_empty),
        "hasForecast": has_forecast(card),
        "hasConspire": has_conspire(card),
        "hasDemonstrate": has_demonstrate(card),
        "hasGift": has_gift(card),
        "hasFuse": has_fuse(card),
        "hasAwaken": has_awaken(card),
        "hasOffering": has_offering(card),
        "hasImpending": has_impending(card),
        "hasForMirrodin": has_for_mirrodin(card),
        "conspireAvailable": (
            conspire_color_match(card, ctx.game.zones, controller_idx)
            if ctx.game is not None and has_conspire(card)
            else False
        ),
        "hasDelve": has_delve(card),
        "hasImprovise": has_improvise(card),
        "hasEmerge": has_emerge(card),
        "hasSpectacle": has_spectacle(card),
        "spectacleAvailable": (
            spectacle_available(ctx.game, controller_idx)
            if ctx.game is not None and has_spectacle(card)
            else False
        ),
        "hasSurge": has_surge(card),
        "surgeAvailable": (
            surge_available(ctx.game, controller_idx)
            if ctx.game is not None and has_surge(card)
            else False
        ),
        "hasMorph": has_morph(card) and card.is_creature,
        "hasDisguise": has_disguise(card) and card.is_creature,
        "hasSneak": has_sneak(card),
        "hasDash": has_dash(card),
        "hasBlitz": has_blitz(card),
        "hasEmbalm": has_embalm(card),
        "hasFreerunning": has_freerunning(card),
        "freerunningAvailable": (
            ctx.game is not None
            and ctx.controller_idx == 0
            and ctx.game.players[0].combat_damage_dealt_this_turn
            and has_freerunning(card)
        ),
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
    return payload


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
