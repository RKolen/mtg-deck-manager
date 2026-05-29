"""Casting and stack resolution for InteractiveGame."""

from __future__ import annotations

from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords.casting.casualty import sacrifice_for_casualty
from engine.abilities.keywords.casting import (
    can_cast_via_madness,
    exile_for_suspend,
    madness_mana_needed,
    remove_suspended_card_from_exile,
    resolve_announce_cast_mana,
    resolve_cast_adjustments,
    sacrifice_for_emerge,
    suspend_mana_needed,
    suspend_setup_error,
    suspend_time_counters,
    tick_suspend_counters,
)
from engine.abilities.keywords.casting.cast_adjustments import CastAdjustmentInput
from engine.abilities.keywords.ability_words.spell_words import apply_spell_hosted_ability_words
from engine.game._hand_card import load_hand_card_for_action, run_with_hand_card
from engine.game.cast_announce_validate import (
    HandCastPlacement,
    PaidAnnounceCast,
    validate_announce_cast,
)
from engine.game.cast_flow import AnnounceCastCompletion, announce_mana_options
from engine.core.game_object import (
    CardObject,
    SpellAlternateCast,
    SpellCastPayment,
)
from engine.game.helpers import (
    CastAnnounceOptions,
    SpellCastContext,
    can_cast_now,
    require_card_info,
)
from engine.game.spell_stack_graveyard import GraveyardCastMixin
from engine.game.spell_stack_resolve import SpellResolveMixin


@dataclass(frozen=True)
class MadnessCastRequest:
    """Targets and timing for a madness cast from hand."""

    hand_idx: int
    target_uid_str: str | None
    target_player_idx: int | None
    auto_resolve: bool


def _announce_cast_detail(
    card_name: str,
    paid: PaidAnnounceCast,
    sacrificed_name: str,
) -> str:
    """Build a log detail string for an announced cast."""
    mods = paid.modifiers
    detail = f"{card_name} on stack"
    if mods.miracle:
        detail = f"{detail} (miracle)"
    if mods.spectacle:
        detail = f"{detail} (spectacle)"
    if mods.morph:
        detail = f"{detail} (morph)"
    if mods.disguise:
        detail = f"{detail} (disguise)"
    if mods.dash:
        detail = f"{detail} (dash)"
    if mods.blitz:
        detail = f"{detail} (blitz)"
    if mods.freerunning:
        detail = f"{detail} (freerunning)"
    if mods.replicate_times:
        detail = f"{detail} (replicate x{mods.replicate_times})"
    if mods.overloaded:
        detail = f"{detail} (overloaded)"
    if mods.bestow:
        detail = f"{detail} (bestow)"
    if mods.entwined:
        detail = f"{detail} (entwined)"
    if mods.kicker_times:
        detail = f"{detail} (kicked x{mods.kicker_times})"
    if mods.buyback:
        detail = f"{detail} (buyback)"
    if mods.emerge:
        detail = f"{detail} (emerge, sacrificed {sacrificed_name})"
    if mods.casualty:
        detail = f"{detail} (casualty, sacrificed {sacrificed_name})"
    if mods.mutate:
        detail = f"{detail} (mutate)"
    if mods.spree_modes:
        detail = f"{detail} (spree modes {list(mods.spree_modes)})"
    return detail


class SpellStackMixin(GraveyardCastMixin, SpellResolveMixin):
    """Stack placement, casting announcements, and spell resolution."""

    def _announce_cast(
        self,
        hand_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
        cast_options: CastAnnounceOptions | None = None,
    ) -> dict:
        """Pay costs and place a spell on the stack."""
        opts = cast_options or CastAnnounceOptions()
        card, card_info, err = load_hand_card_for_action(self, hand_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        assert can_cast_now(card_info, self.phase, self.state.stack.is_empty)
        paid, val_err = validate_announce_cast(
            self.state.zones,
            0,
            card_info,
            opts,
            self.state.players[0].combat_damage_dealt_this_turn,
            target_uid_str,
            self.state,
        )
        if val_err:
            return {**self.to_client(), "error": val_err}
        assert paid is not None
        mana_needed, life_cost = resolve_announce_cast_mana(
            card_info,
            announce_mana_options(paid, opts, self.state, 0),
        )
        return self._place_validated_hand_cast(
            HandCastPlacement(
                card=card,
                card_info=card_info,
                paid=paid,
                opts=opts,
                hand_idx=hand_idx,
                target_player_idx=target_player_idx,
                mana_needed=mana_needed,
                life_cost=life_cost,
                auto_resolve=auto_resolve,
            ),
        )

    def _place_validated_hand_cast(self, placement: HandCastPlacement) -> dict:
        """Pay adjustments, put the spell on the stack, and optionally auto-pass."""
        card = placement.card
        card_info = placement.card_info
        paid = placement.paid
        opts = placement.opts
        hand_idx = placement.hand_idx
        target_player_idx = placement.target_player_idx
        mana_needed = placement.mana_needed
        life_cost = placement.life_cost
        auto_resolve = placement.auto_resolve
        adjustments = resolve_cast_adjustments(
            card_info,
            mana_needed,
            CastAdjustmentInput(
                convoke_creature_ids=opts.modifiers.reductions.convoke_creature_ids,
                delve_graveyard_indices=opts.modifiers.reductions.delve_graveyard_indices,
                improvise_artifact_ids=opts.modifiers.reductions.improvise_artifact_ids,
                sneak_land_hand_indices=opts.modifiers.reductions.sneak_land_hand_indices,
                spell_hand_idx=hand_idx,
            ),
            self.state.zones,
            0,
        )
        if adjustments.error:
            return {**self.to_client(), "error": adjustments.error}
        mana_needed = adjustments.mana_needed
        mana_err = self._tap_mana_or_error(0, mana_needed)
        if mana_err is not None:
            return mana_err
        self.state.players[0].spells_cast_this_turn += 1
        self._pay_phyrexian(0, life_cost, card_info.name)
        sacrificed_name = ""
        if paid.emerge_sacrifice_id is not None:
            sacrificed = sacrifice_for_emerge(
                self.state.zones,
                self.state,
                paid.emerge_sacrifice_id,
            )
            sacrificed_name = sacrificed.name
        elif paid.casualty_sacrifice_id is not None:
            sacrificed = sacrifice_for_casualty(
                self.state.zones,
                self.state,
                paid.casualty_sacrifice_id,
            )
            sacrificed_name = sacrificed.name
        mods = paid.modifiers
        stack_context = SpellCastContext(
            payment=SpellCastPayment(
                kicker_times=mods.kicker_times,
                entwined=mods.entwined,
                overloaded=mods.overloaded,
                bestow=mods.bestow,
                paid_buyback=mods.buyback,
                emerge=mods.emerge,
                evoke=mods.evoke,
                mutate=mods.mutate,
                casualty=mods.casualty,
                morph_face_down=mods.morph,
                disguise_face_down=mods.disguise,
                dash=mods.dash,
                blitz=mods.blitz,
            ),
            replicate_times=mods.replicate_times,
            spree_mode_indices=mods.spree_modes,
        )
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=paid.cast_target_uid,
            target_player_idx=target_player_idx,
            context=stack_context,
        )
        cast_detail = _announce_cast_detail(card_info.name, paid, sacrificed_name)
        if adjustments.delve_cards_exiled:
            cast_detail = (
                f"{cast_detail} (delve x{adjustments.delve_cards_exiled})"
            )
        if adjustments.convoke_creature_ids:
            cast_detail = (
                f"{cast_detail} (convoke x{len(adjustments.convoke_creature_ids)})"
            )
        if adjustments.improvise_artifact_ids:
            cast_detail = (
                f"{cast_detail} (improvise x{len(adjustments.improvise_artifact_ids)})"
            )
        if adjustments.sneak_lands_exiled:
            cast_detail = f"{cast_detail} (sneak x{adjustments.sneak_lands_exiled})"
        self._log("player", "cast", cast_detail)
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        for word_detail in apply_spell_hosted_ability_words(self.state, card_info, 0):
            self._log("player", "ability_word", word_detail)
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

    def _announce_madness_cast(
        self,
        hand_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Cast a card from hand for its madness cost."""
        request = MadnessCastRequest(
            hand_idx=hand_idx,
            target_uid_str=target_uid_str,
            target_player_idx=target_player_idx,
            auto_resolve=auto_resolve,
        )
        return run_with_hand_card(
            self,
            hand_idx,
            lambda card, card_info: self._resolve_madness_cast(card, card_info, request),
        )

    def _resolve_madness_cast(
        self,
        card: CardObject,
        card_info: CardInfo,
        request: MadnessCastRequest,
    ) -> dict:
        if not can_cast_via_madness(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot cast for madness now"}
        mana_needed, life_cost = madness_mana_needed(card_info)
        mana_err = self._tap_mana_or_error(0, mana_needed)
        if mana_err is not None:
            return mana_err
        return self._complete_announce_cast(
            AnnounceCastCompletion(
                card=card,
                card_info=card_info,
                player_idx=0,
                target_uid_str=request.target_uid_str,
                target_player_idx=request.target_player_idx,
                context=SpellCastContext(alternate=SpellAlternateCast(madness=True)),
                log_action="madness",
                log_detail=f"{card_info.name} on stack",
                auto_resolve=request.auto_resolve,
                life_cost=life_cost,
            ),
        )

    def action_suspend(self, hand_idx: int) -> dict:
        """Exile a card from hand with suspend counters after paying the suspend cost."""
        card = self._zones(0).hand[hand_idx]
        if not isinstance(card, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(card)
        setup_err = suspend_setup_error(
            self.state.zones,
            0,
            hand_idx,
            phase=self.phase,
            stack_is_empty=self.state.stack.is_empty,
        )
        if setup_err:
            return {**self.to_client(), "error": setup_err}
        counters = suspend_time_counters(card_info)
        if counters <= 0:
            return {**self.to_client(), "error": f"{card_info.name} has no suspend counters"}
        mana_needed, life_cost = suspend_mana_needed(card_info)
        mana_err = self._tap_mana_or_error(0, mana_needed)
        if mana_err is not None:
            return mana_err
        self._pay_phyrexian(0, life_cost, card_info.name)
        exile_for_suspend(self.state.zones, 0, hand_idx, counters)
        self._log("player", "suspend", f"Suspended {card_info.name} ({counters} counters)")
        return self.to_client()

    def _cast_suspended_spell(
        self,
        player_idx: int,
        card: CardObject,
        auto_resolve: bool,
    ) -> None:
        """Put a suspended card on the stack free when its last time counter is removed."""
        card_info = require_card_info(card)
        remove_suspended_card_from_exile(self.state.zones, player_idx, card)
        self.state.players[player_idx].spells_cast_this_turn += 1
        targets = self._put_spell_on_stack(
            player_idx=player_idx,
            card=card,
            target_uid_str=None,
            target_player_idx=None,
            context=SpellCastContext(
                alternate=SpellAlternateCast(suspend=True),
                from_exile=True,
            ),
        )
        actor = "player" if player_idx == 0 else "opponent"
        self._log(actor, "suspend_cast", f"{card_info.name} on stack (suspend)")
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if auto_resolve:
            self._auto_pass_stack()

    def _tick_suspend_upkeep(self, player_idx: int) -> None:
        """Remove one time counter from suspended cards and cast those that reach zero."""
        ready = tick_suspend_counters(self.state.zones, player_idx)
        for card in ready:
            self._cast_suspended_spell(player_idx, card, auto_resolve=True)
