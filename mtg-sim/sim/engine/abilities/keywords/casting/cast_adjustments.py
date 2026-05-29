"""Orchestrate optional cast cost reductions (delve, convoke, improvise)."""

from __future__ import annotations

from dataclasses import dataclass, field

from deck_registry import CardInfo
from engine.game.cast_context import CastManaReductionIds
from engine.abilities.keywords.casting.convoke import resolve_convoke_for_cast
from engine.abilities.keywords.casting.delve import resolve_delve_for_cast
from engine.abilities.keywords.casting.improvise import resolve_improvise_for_cast
from engine.abilities.keywords.casting.assist import resolve_assist_for_cast
from engine.abilities.keywords.casting.sneak import SneakCastInput, resolve_sneak_for_cast
from engine.core.zones import ZoneManager


@dataclass(frozen=True)
class CastAdjustmentResult:
    """Outcome of optional mana reductions before tapping lands."""

    mana_needed: int
    convoke_creature_ids: tuple[int, ...] = ()
    delve_cards_exiled: int = 0
    improvise_artifact_ids: tuple[int, ...] = ()
    sneak_lands_exiled: int = 0
    assist_mana_applied: int = 0
    error: str | None = None


@dataclass(frozen=True)
class CastAdjustmentInput:
    """Optional cost reductions submitted with a cast announcement."""

    reductions: CastManaReductionIds = field(default_factory=CastManaReductionIds)
    spell_hand_idx: int = -1


def resolve_cast_adjustments(
    card: CardInfo,
    mana_needed: int,
    options: CastAdjustmentInput,
    zones: ZoneManager,
    player_idx: int,
) -> CastAdjustmentResult:
    """Apply delve, convoke, and improvise in order; return land mana still owed."""
    reductions = options.reductions
    mana, delve_count, err = resolve_delve_for_cast(
        card,
        mana_needed,
        list(reductions.delve_graveyard_indices),
        zones,
        player_idx,
    )
    if err is not None:
        return CastAdjustmentResult(mana_needed, error=err)

    mana, convoke_ids, err = resolve_convoke_for_cast(
        card,
        mana,
        list(reductions.convoke_creature_ids),
        zones,
        player_idx,
    )
    if err is not None:
        return CastAdjustmentResult(mana_needed, delve_cards_exiled=delve_count, error=err)

    mana, improvise_ids, err = resolve_improvise_for_cast(
        card,
        mana,
        list(reductions.improvise_artifact_ids),
        zones,
        player_idx,
    )
    if err is not None:
        return CastAdjustmentResult(
            mana_needed,
            convoke_creature_ids=tuple(convoke_ids),
            delve_cards_exiled=delve_count,
            error=err,
        )

    mana, sneak_count, err = resolve_sneak_for_cast(
        card,
        mana,
        zones,
        player_idx,
        SneakCastInput(
            options.spell_hand_idx,
            reductions.sneak_land_hand_indices,
        ),
    )
    if err is not None:
        return CastAdjustmentResult(
            mana_needed,
            convoke_creature_ids=tuple(convoke_ids),
            delve_cards_exiled=delve_count,
            improvise_artifact_ids=tuple(improvise_ids),
            error=err,
        )

    mana, assist_applied, err = resolve_assist_for_cast(
        card,
        mana,
        reductions.assist_mana,
    )
    if err is not None:
        return CastAdjustmentResult(
            mana_needed,
            convoke_creature_ids=tuple(convoke_ids),
            delve_cards_exiled=delve_count,
            improvise_artifact_ids=tuple(improvise_ids),
            sneak_lands_exiled=sneak_count,
            error=err,
        )

    return CastAdjustmentResult(
        mana,
        convoke_creature_ids=tuple(convoke_ids),
        delve_cards_exiled=delve_count,
        improvise_artifact_ids=tuple(improvise_ids),
        sneak_lands_exiled=sneak_count,
        assist_mana_applied=assist_applied,
    )
