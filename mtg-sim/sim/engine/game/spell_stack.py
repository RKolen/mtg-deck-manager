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
from engine.abilities.keywords.casting.cast_adjustments import (
    CastAdjustmentInput,
    CastAdjustmentResult,
)
from engine.abilities.keywords.ability_words.spell_words import apply_spell_hosted_ability_words
from engine.game._hand_card import load_hand_card_for_action, run_with_hand_card
from engine.game.cast_announce_validate import (
    HandCastPlacement,
    PaidAnnounceCast,
    _CastManaInfo,
    _CastPlacementInfo,
    _CastValidationContext,
    validate_announce_cast,
)
from engine.game.cast_detail import announce_cast_detail_suffix
from engine.game.cast_flow import (
    AnnounceCastCompletion,
    _CastLog,
    _TargetRef,
    announce_mana_options,
)
from engine.core.game_object import (
    CardObject,
    SpellAlternateCast,
    SpellCastPayment,
    _ExileAlts,
    _CostMods,
    _AlternateModes,
    _KeywordPays,
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


@dataclass(frozen=True)
class _HandCastRequest:
    """Target and timing options for a hand cast."""

    target_uid_str: str | None
    target_player_idx: int | None
    auto_resolve: bool
    cast_options: CastAnnounceOptions | None = None


def _announce_cast_detail(
    card_name: str,
    paid: PaidAnnounceCast,
    sacrificed_name: str,
) -> str:
    """Build a log detail string for an announced cast."""
    return f"{card_name} on stack{announce_cast_detail_suffix(paid.modifiers, sacrificed_name)}"


def _build_cast_detail(
    card_name: str,
    paid: PaidAnnounceCast,
    sacrificed_name: str,
    adjustments: CastAdjustmentResult,
) -> str:
    """Build the full cast detail string including cost adjustments."""
    detail = _announce_cast_detail(card_name, paid, sacrificed_name)
    if adjustments.delve_cards_exiled:
        detail = f"{detail} (delve x{adjustments.delve_cards_exiled})"
    if adjustments.convoke_creature_ids:
        detail = f"{detail} (convoke x{len(adjustments.convoke_creature_ids)})"
    if adjustments.improvise_artifact_ids:
        detail = f"{detail} (improvise x{len(adjustments.improvise_artifact_ids)})"
    if adjustments.sneak_lands_exiled:
        detail = f"{detail} (sneak x{adjustments.sneak_lands_exiled})"
    if adjustments.assist_mana_applied:
        detail = f"{detail} (assist x{adjustments.assist_mana_applied})"
    return detail


class SpellStackMixin(GraveyardCastMixin, SpellResolveMixin):
    """Stack placement, casting announcements, and spell resolution."""

    def _announce_cast(
        self,
        hand_idx: int,
        request: _HandCastRequest,
    ) -> dict:
        """Pay costs and place a spell on the stack."""
        target_uid_str = request.target_uid_str
        target_player_idx = request.target_player_idx
        auto_resolve = request.auto_resolve
        opts = request.cast_options or CastAnnounceOptions()
        card, card_info, err = load_hand_card_for_action(self, hand_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        assert can_cast_now(card_info, self.phase, self.state.stack.is_empty)
        paid, val_err = validate_announce_cast(
            _CastValidationContext(
                zones=self.state.zones,
                game=self.state,
                player_idx=0,
            ),
            card_info,
            opts,
            self.state.players[0].combat_damage_dealt_this_turn,
            target_uid_str,
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
                placement=_CastPlacementInfo(
                    card=card,
                    hand_idx=hand_idx,
                    target_player_idx=target_player_idx,
                ),
                card_info=card_info,
                paid=paid,
                opts=opts,
                cost=_CastManaInfo(mana_needed=mana_needed, life_cost=life_cost),
                auto_resolve=auto_resolve,
            ),
        )

    def _apply_emerge_casualty_sacrifice(self, paid: PaidAnnounceCast) -> str:
        """Sacrifice for emerge or casualty and return the sacrificed card name."""
        if paid.emerge_sacrifice_id is not None:
            sacrificed = sacrifice_for_emerge(
                self.state.zones,
                self.state,
                paid.emerge_sacrifice_id,
            )
            return sacrificed.name
        if paid.casualty_sacrifice_id is not None:
            sacrificed = sacrifice_for_casualty(
                self.state.zones,
                self.state,
                paid.casualty_sacrifice_id,
            )
            return sacrificed.name
        return ""

    def _place_validated_hand_cast(self, placement: HandCastPlacement) -> dict:
        """Pay adjustments, put the spell on the stack, and optionally auto-pass."""
        opts = placement.opts
        adjustments = resolve_cast_adjustments(
            placement.card_info,
            placement.mana_needed,
            CastAdjustmentInput(
                reductions=opts.modifiers.reductions,
                spell_hand_idx=placement.hand_idx,
            ),
            self.state.zones,
            0,
        )
        if adjustments.error:
            return {**self.to_client(), "error": adjustments.error}
        mana_err = self._tap_mana_or_error(0, adjustments.mana_needed)
        if mana_err is not None:
            return mana_err
        self.state.players[0].spells_cast_this_turn += 1
        self._pay_phyrexian(0, placement.life_cost, placement.card_info.name)
        sacrificed_name = self._apply_emerge_casualty_sacrifice(placement.paid)
        mods = placement.paid.modifiers
        stack_context = SpellCastContext(
            payment=SpellCastPayment(
                costs=_CostMods(
                    kicker_times=mods.kicker_times,
                    entwined=mods.entwined,
                    overloaded=mods.overloaded,
                    bestow=mods.bestow,
                    paid_buyback=mods.buyback,
                ),
                modes=_AlternateModes(
                    emerge=mods.emerge,
                    evoke=mods.evoke,
                    mutate=mods.mutate,
                    casualty=mods.casualty,
                    morph_face_down=mods.morph,
                ),
                keywords=_KeywordPays(
                    disguise_face_down=mods.disguise,
                    dash=mods.dash,
                    blitz=mods.blitz,
                    cleave=mods.cleave,
                    conspire=mods.conspire,
                ),
            ),
            replicate_times=mods.replicate_times,
            spree_mode_indices=mods.spree_modes,
        )
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=placement.card,
            target_ref=_TargetRef(placement.paid.cast_target_uid, placement.target_player_idx),
            context=stack_context,
        )
        cast_detail = _build_cast_detail(
            placement.card_info.name,
            placement.paid,
            sacrificed_name,
            adjustments,
        )
        self._log("player", "cast", cast_detail)
        self.state.fire_spell_cast_triggers(placement.card, tuple(targets))
        for word_detail in apply_spell_hosted_ability_words(
            self.state, placement.card_info, 0
        ):
            self._log("player", "ability_word", word_detail)
        if placement.auto_resolve:
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
                target_uid_str=(
                    request.target_uid_str
                ),
                target_player_idx=request.target_player_idx,
                context=SpellCastContext(
                    alternate=SpellAlternateCast(exile=_ExileAlts(madness=True))
                ),
                log_opts=_CastLog(
                    log_action="madness",
                    log_detail=f"{card_info.name} on stack",
                    auto_resolve=request.auto_resolve,
                    life_cost=life_cost,
                ),
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
            target_ref=_TargetRef(None, None),
            context=SpellCastContext(
                alternate=SpellAlternateCast(exile=_ExileAlts(suspend=True)),
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
