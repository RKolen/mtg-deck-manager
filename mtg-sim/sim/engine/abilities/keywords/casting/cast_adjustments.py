"""Orchestrate optional cast cost reductions (delve, convoke, improvise)."""

from __future__ import annotations

from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords.casting.convoke import resolve_convoke_for_cast
from engine.abilities.keywords.casting.delve import resolve_delve_for_cast
from engine.abilities.keywords.casting.improvise import resolve_improvise_for_cast
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
    error: str | None = None


@dataclass(frozen=True)
class CastAdjustmentInput:
    """Optional cost reductions submitted with a cast announcement."""

    convoke_creature_ids: tuple[int, ...] = ()
    delve_graveyard_indices: tuple[int, ...] = ()
    improvise_artifact_ids: tuple[int, ...] = ()
    sneak_land_hand_indices: tuple[int, ...] = ()
    spell_hand_idx: int = -1


def resolve_cast_adjustments(
    card: CardInfo,
    mana_needed: int,
    options: CastAdjustmentInput,
    zones: ZoneManager,
    player_idx: int,
) -> CastAdjustmentResult:
    """Apply delve, convoke, and improvise in order; return land mana still owed."""
    mana, delve_count, err = resolve_delve_for_cast(
        card,
        mana_needed,
        list(options.delve_graveyard_indices),
        zones,
        player_idx,
    )
    if err is not None:
        return CastAdjustmentResult(mana_needed, error=err)

    mana, convoke_ids, err = resolve_convoke_for_cast(
        card,
        mana,
        list(options.convoke_creature_ids),
        zones,
        player_idx,
    )
    if err is not None:
        return CastAdjustmentResult(mana_needed, delve_cards_exiled=delve_count, error=err)

    mana, improvise_ids, err = resolve_improvise_for_cast(
        card,
        mana,
        list(options.improvise_artifact_ids),
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
            options.sneak_land_hand_indices,
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

    return CastAdjustmentResult(
        mana,
        convoke_creature_ids=tuple(convoke_ids),
        delve_cards_exiled=delve_count,
        improvise_artifact_ids=tuple(improvise_ids),
        sneak_lands_exiled=sneak_count,
    )
