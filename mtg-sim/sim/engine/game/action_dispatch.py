"""Dispatch HTTP game actions to InteractiveGame methods."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from engine.game.cast_context import (
    CastAnnounceOptions,
    CastManaReductionIds,
    CastModifierIds,
    CastTargetingIds,
    _SacrificeTargetIds,
    HandAlternateCastChoices,
    HandCastCostChoices,
    _CostConditionAlts,
    _PaidSacrificeCosts,
    _RepeatCostChoices,
)
from engine.game.face_alternate_cast import FaceAlternateCastFlags

if TYPE_CHECKING:
    from engine.game.interactive import InteractiveGame


def cast_announce_options_from_request(req) -> CastAnnounceOptions:
    """Build cast announce options from a GameActionRequest."""
    convoke_ids = tuple(int(uid) for uid in req.convokeCreatureIds)
    improvise_ids = tuple(int(uid) for uid in req.improviseArtifactIds)
    emerge_ids = tuple(int(uid) for uid in req.emergeSacrificeIds)
    casualty_ids = tuple(int(uid) for uid in req.casualtySacrificeIds)
    bargain_ids = tuple(int(uid) for uid in req.bargainSacrificeIds)
    harmonize_ids = tuple(int(uid) for uid in req.harmonizeCreatureIds)
    return CastAnnounceOptions(
        costs=HandCastCostChoices(
            entwined=req.entwined,
            overloaded=req.overloaded,
            paid_buyback=req.paidBuyback,
            paid=_PaidSacrificeCosts(
                paid_casualty=req.paidCasualty,
                paid_conspire=req.paidConspire,
                paid_bargain=req.paidBargain,
                paid_demonstrate=req.paidDemonstrate,
                paid_awaken=req.paidAwaken,
            ),
            repeat=_RepeatCostChoices(
                kicker_times=req.kickerTimes,
                replicate_times=req.replicateTimes,
            ),
        ),
        alternate=HandAlternateCastChoices(
            cast_for_emerge=req.castForEmerge,
            cast_for_evoke=req.castForEvoke,
            cast_for_mutate=req.castForMutate,
            cast_for_cleave=req.castForCleave,
            conditions=_CostConditionAlts(
                cast_for_miracle=req.castForMiracle,
                cast_for_freerunning=req.castForFreerunning,
                cast_for_spectacle=req.castForSpectacle,
            ),
            face=FaceAlternateCastFlags(
                cast_for_morph=req.castForMorph,
                cast_for_disguise=req.castForDisguise,
                cast_for_dash=req.castForDash,
                cast_for_blitz=req.castForBlitz,
            ),
        ),
        modifiers=CastModifierIds(
            targeting=CastTargetingIds(
                bestow_target_uid=req.bestowTargetUid,
                mutate_target_uid=req.mutateTargetUid,
                escalate_extra_targets=req.escalateExtraTargets,
                spree_mode_indices=tuple(req.spreeModeIndices),
                harmonize_creature_ids=harmonize_ids,
                sacrifices=_SacrificeTargetIds(
                    emerge_sacrifice_ids=emerge_ids,
                    casualty_sacrifice_ids=casualty_ids,
                    bargain_sacrifice_ids=bargain_ids,
                ),
            ),
            reductions=CastManaReductionIds(
                convoke_creature_ids=convoke_ids,
                delve_graveyard_indices=tuple(req.delveGraveyardIndices),
                improvise_artifact_ids=improvise_ids,
                sneak_land_hand_indices=tuple(req.sneakLandHandIndices),
                assist_mana=req.assistMana,
                awaken_land_hand_idx=req.awakenLandHandIdx,
            ),
        ),
    )


def _dispatch_simple(game: InteractiveGame, req) -> dict | None:
    simple: dict[str, Callable[[], dict]] = {
        "keep": game.action_keep,
        "mulligan": game.action_mulligan,
        "draw": game.action_draw,
        "pass_priority": game.action_pass_priority,
        "go_to_attack": game.action_go_to_attack,
        "confirm_attack": game.action_confirm_attack,
        "skip_attack": game.action_skip_attack,
    }
    handler = simple.get(req.action)
    return handler() if handler is not None else None


def _dispatch_hand_actions(game: InteractiveGame, req) -> dict | None:
    handlers: dict[str, Callable[[], dict]] = {
        "play_land": lambda: game.action_play_land(req.handIdx),
        "cast": lambda: game.action_cast(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
            cast_options=cast_announce_options_from_request(req),
        ),
        "cast_madness": lambda: game.action_cast_madness(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
        ),
        "suspend": lambda: game.action_suspend(req.handIdx),
        "cycle": lambda: game.action_cycle(req.handIdx),
        "forecast": lambda: game.action_forecast(req.handIdx),
        "channel": lambda: game.action_channel(req.handIdx, req.targetPlayer),
        "bloodrush": lambda: game.action_bloodrush(
            req.handIdx,
            req.targetUid,
        ),
        "ninjutsu": lambda: game.action_ninjutsu(
            req.handIdx,
            req.targetUid,
        ),
        "unearth": lambda: game.action_unearth(req.handIdx),
        "scavenge": lambda: game.action_scavenge(req.handIdx, req.targetUid),
        "dredge": lambda: game.action_dredge(req.handIdx),
        "encore": lambda: game.action_encore(req.handIdx),
        "eternalize": lambda: game.action_eternalize(req.handIdx),
        "foretell": lambda: game.action_foretell(req.handIdx),
        "plot": lambda: game.action_plot(req.handIdx),
        "embalm": lambda: game.action_embalm(req.handIdx),
    }
    handler = handlers.get(req.action)
    if handler is None or req.handIdx is None:
        return None
    return handler()


def _dispatch_permanent_actions(game: InteractiveGame, req) -> dict | None:
    if req.permanentUid is None:
        return None
    uid = req.permanentUid
    handlers: dict[str, Callable[[], dict]] = {
        "crew": lambda: game.action_crew(
            uid,
            [str(cid) for cid in (req.convokeCreatureIds or [])],
        ),
        "mount": lambda: game.action_mount(
            uid,
            [str(cid) for cid in (req.convokeCreatureIds or [])],
        ),
        "level_up": lambda: game.action_level_up(uid),
        "activate": lambda: game.action_activate(
            uid,
            req.handIdx or 0,
            host_uid=req.targetUid,
        ),
        "outlast": lambda: game.action_outlast(uid),
        "turn_up_morph": lambda: game.action_turn_up_morph(uid),
        "boast": lambda: game.action_boast(uid),
        "craft": lambda: game.action_craft(
            uid,
            [str(aid) for aid in (req.craftArtifactIds or [])],
        ),
        "toggle_attacker": lambda: game.action_toggle_attacker(uid),
    }
    handler = handlers.get(req.action)
    return handler() if handler is not None else None


def _dispatch_alt_cast(game: InteractiveGame, req) -> dict | None:
    if req.handIdx is None:
        return None
    alt_handlers: dict[str, Callable[[], dict]] = {
        "cast_disturb": lambda: game.action_cast_disturb(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
        ),
        "cast_flashback": lambda: game.action_cast_flashback(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
        ),
        "cast_escape": lambda: game.action_cast_escape(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
            escape_exile_indices=req.escapeExileIndices,
        ),
        "cast_jump_start": lambda: game.action_cast_jump_start(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
            discard_hand_idx=req.discardHandIdx,
        ),
        "cast_retrace": lambda: game.action_cast_retrace(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
            discard_hand_idx=req.discardHandIdx,
        ),
        "cast_foretell": lambda: game.action_cast_foretell(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
        ),
        "cast_plot": lambda: game.action_cast_plot(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
        ),
        "cast_aftermath": lambda: game.action_cast_aftermath(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
        ),
        "cast_harmonize": lambda: game.action_cast_harmonize(
            req.handIdx,
            req.targetUid,
            req.targetPlayer,
            harmonize_creature_ids=req.harmonizeCreatureIds,
        ),
    }
    handler = alt_handlers.get(req.action)
    return handler() if handler is not None else None


def dispatch_game_action(game: InteractiveGame, req) -> dict | None:
    """Return updated client state, or None if the action is not handled here."""
    for dispatcher in (
        _dispatch_simple,
        _dispatch_hand_actions,
        _dispatch_permanent_actions,
        _dispatch_alt_cast,
    ):
        result = dispatcher(game, req)
        if result is not None:
            return result
    return None
