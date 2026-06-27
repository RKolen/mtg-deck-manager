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
from engine.abilities.keywords.casting.mayhem import has_mayhem
from engine.abilities.keywords.casting.prototype import has_prototype
from engine.abilities.keywords.casting.splice import has_splice
from engine.abilities.keywords.casting.compleated import has_compleated
from engine.abilities.keywords.casting.paradigm import has_paradigm
from engine.abilities.keywords.casting.tiered import has_tiered
from engine.abilities.keywords.casting.undaunted import has_undaunted
from engine.abilities.keywords.casting.specialize import has_specialize
from engine.abilities.keywords.casting.web_slinging import has_web_slinging
from engine.abilities.keywords.casting.more_than_meets_the_eye import has_more_than_meets_the_eye
from engine.abilities.keywords.other.commander_ninjutsu import has_commander_ninjutsu
from engine.abilities.keywords.other.hidden_agenda import has_double_agenda
from engine.abilities.keywords.other.megamorph import has_megamorph
from engine.abilities.keywords.other.multikicker import has_multikicker
from engine.abilities.keywords.other.daybound import has_daybound_card
from engine.abilities.keywords.other.affinity import has_affinity_for_artifacts
from engine.abilities.keywords.other.afflict import has_afflict_card
from engine.abilities.keywords.other.amplify import has_amplify_card
from engine.abilities.keywords.other.annihilator import has_annihilator_card
from engine.abilities.keywords.other.ascend import has_ascend_card
from engine.abilities.keywords.other.augment import has_augment_card
from engine.abilities.keywords.other.battle_cry import has_battle_cry_card
from engine.abilities.keywords.other.boast import has_boast_card
from engine.abilities.keywords.other.blitz import has_blitz_card
from engine.abilities.keywords.other.bushido import has_bushido_card
from engine.abilities.keywords.other.cipher import has_cipher_card
from engine.abilities.keywords.other.companion import has_companion_card
from engine.abilities.keywords.other.craft import has_craft_card
from engine.abilities.keywords.other.dash import has_dash_card
from engine.abilities.keywords.other.decayed import has_decayed_card
from engine.abilities.keywords.other.dethrone import has_dethrone_card
from engine.abilities.keywords.other.dredge import has_dredge_card
from engine.abilities.keywords.other.echo import has_echo_card
from engine.abilities.keywords.other.encore import has_encore_card
from engine.abilities.keywords.other.eternalize import has_eternalize_card
from engine.abilities.keywords.other.enlist import has_enlist_card
from engine.abilities.keywords.other.exalted import has_exalted_card
from engine.abilities.keywords.other.exhaust import has_exhaust_card
from engine.abilities.keywords.other.extort import has_extort_card
from engine.abilities.keywords.other.fabricate import has_fabricate_card
from engine.abilities.keywords.other.flanking import has_flanking_card
from engine.abilities.keywords.other.frenzy import has_frenzy_card
from engine.abilities.keywords.other.devour import has_devour_card
from engine.abilities.keywords.other.graft import has_graft_card
from engine.abilities.keywords.other.mentor import has_mentor_card
from engine.abilities.keywords.other.mobilize import has_mobilize_card
from engine.abilities.keywords.other.myriad import has_myriad_card
from engine.abilities.keywords.other.offspring import has_offspring_card
from engine.abilities.keywords.other.outlast import has_outlast_card
from engine.abilities.keywords.other.prowl import has_prowl_card
from engine.abilities.keywords.other.renown import has_renown_card
from engine.abilities.keywords.other.prowess import has_prowess_card
from engine.abilities.keywords.other.nightbound import has_nightbound_card
from engine.abilities.keywords.other.partner import has_partner_card
from engine.abilities.keywords.other.partner_with import has_partner_with
from engine.abilities.keywords.casting.warp import has_warp
from engine.abilities.keywords.casting.squad import has_squad
from engine.abilities.keywords.casting.offering import has_offering
from engine.abilities.keywords.casting.ripple import has_ripple
from engine.abilities.keywords.casting.escalate import has_escalate
from engine.abilities.keywords.other.disguise import has_disguise_card
from engine.abilities.keywords.other.embalm import has_embalm_card
from engine.abilities.keywords.other.evoke import has_evoke_card
from engine.abilities.keywords.other.forecast import can_forecast, has_forecast_card
from engine.abilities.keywords.casting.convoke import has_convoke
from engine.abilities.keywords.casting.delve import has_delve
from engine.abilities.keywords.casting.emerge import has_emerge
from engine.abilities.keywords.casting.evoke import evoke_mana_needed
from engine.abilities.keywords.casting.improvise import has_improvise
from engine.abilities.keywords.casting.freerunning import has_freerunning
from engine.abilities.keywords.casting.sneak import has_sneak
from engine.abilities.keywords.casting.spectacle import has_spectacle, spectacle_available
from engine.abilities.keywords.casting.surge import has_surge, surge_available
from engine.abilities.keywords.other.morph import has_morph_card
from engine.abilities.keywords.other.ninjutsu import (
    can_ninjutsu,
    has_ninjutsu,
    has_ninjutsu_card,
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
    has_evoke_kw = has_evoke_card(card)
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
        "hasForecast": has_forecast_card(card),
        "hasConspire": has_conspire(card),
        "hasDemonstrate": has_demonstrate(card),
        "hasGift": has_gift(card),
        "hasFuse": has_fuse(card),
        "hasAwaken": has_awaken(card),
        "hasOffering": has_offering(card),
        "hasImpending": has_impending(card),
        "hasForMirrodin": has_for_mirrodin(card),
        "hasRipple": has_ripple(card),
        "hasPrototype": has_prototype(card),
        "hasSplice": has_splice(card),
        "hasMayhem": has_mayhem(card),
        "hasSquad": has_squad(card),
        "hasWarp": has_warp(card),
        "hasSpecialize": has_specialize(card),
        "hasCompleated": has_compleated(card),
        "hasTiered": has_tiered(card),
        "hasUndaunted": has_undaunted(card),
        "hasParadigm": has_paradigm(card),
        "hasWebSlinging": has_web_slinging(card),
        "hasMoreThanMeetsTheEye": has_more_than_meets_the_eye(card),
        "hasCommanderNinjutsu": has_commander_ninjutsu(card),
        "hasMegamorph": has_megamorph(card),
        "hasPartnerWith": has_partner_with(card),
        "hasDoubleAgenda": has_double_agenda(card),
        "hasMultikicker": has_multikicker(card),
        "hasAffinityForArtifacts": has_affinity_for_artifacts(card.oracle_text),
        "hasProwess": has_prowess_card(card),
        "hasDaybound": has_daybound_card(card) and card.is_creature,
        "hasNightbound": has_nightbound_card(card) and card.is_creature,
        "hasAfflict": has_afflict_card(card),
        "hasAnnihilator": has_annihilator_card(card),
        "hasCipher": has_cipher_card(card),
        "hasExalted": has_exalted_card(card),
        "hasMobilize": has_mobilize_card(card),
        "hasEnlist": has_enlist_card(card),
        "hasFlanking": has_flanking_card(card),
        "hasFrenzy": has_frenzy_card(card),
        "hasDevour": has_devour_card(card),
        "hasFabricate": has_fabricate_card(card),
        "hasExtort": has_extort_card(card),
        "hasMentor": has_mentor_card(card),
        "hasDethrone": has_dethrone_card(card),
        "hasBattleCry": has_battle_cry_card(card),
        "hasBushido": has_bushido_card(card),
        "hasRenown": has_renown_card(card),
        "hasAmplify": has_amplify_card(card),
        "hasGraft": has_graft_card(card),
        "hasEcho": has_echo_card(card),
        "hasDecayed": has_decayed_card(card),
        "hasAscend": has_ascend_card(card),
        "hasBoast": has_boast_card(card),
        "hasOutlast": has_outlast_card(card),
        "hasMyriad": has_myriad_card(card),
        "hasOffspring": has_offspring_card(card),
        "hasCraft": has_craft_card(card),
        "hasDredge": has_dredge_card(card),
        "hasAugment": has_augment_card(card),
        "hasProwl": has_prowl_card(card),
        "hasExhaust": has_exhaust_card(card),
        "hasEncore": has_encore_card(card),
        "hasEternalize": has_eternalize_card(card),
        "hasPartner": has_partner_card(card),
        "hasCompanion": has_companion_card(card),
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
        "hasMorph": has_morph_card(card) and card.is_creature,
        "hasDisguise": has_disguise_card(card) and card.is_creature,
        "hasNinjutsu": has_ninjutsu_card(card),
        "hasSneak": has_sneak(card),
        "hasDash": has_dash_card(card),
        "hasBlitz": has_blitz_card(card),
        "hasEmbalm": has_embalm_card(card),
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
