"""Casting and stack resolution for InteractiveGame."""

from __future__ import annotations

from dataclasses import dataclass

from deck_registry import CardInfo
from engine.abilities.keywords.casting import (
    aftermath_mana_needed,
    sacrifice_for_emerge,
    FORETELL_SETUP_MANA,
    cast_from_foretell_exile,
    exile_for_foretell,
    foretell_cast_mana_needed,
    foretell_setup_error,
    foretold_cast_error,
    cast_from_plot_exile,
    exile_for_plot,
    plot_setup_error,
    plotted_cast_error,
    mutate_bonus_counters,
    has_spree,
    spree_mode_damage,
    spree_mode_draw,
    spree_mode_is_destroy,
    spree_modes,
    can_cast_aftermath,
    can_cast_via_escape,
    can_cast_via_flashback,
    can_cast_via_jump_start,
    has_aftermath,
    discard_for_jump_start,
    has_jump_start,
    jump_start_discard_error,
    jump_start_mana_needed,
    can_cast_via_retrace,
    discard_land_for_retrace,
    has_retrace,
    retrace_land_discard_error,
    retrace_life_cost,
    retrace_mana_needed,
    entwined_extra_draw,
    can_cast_via_madness,
    madness_mana_needed,
    exile_for_suspend,
    suspend_mana_needed,
    suspend_setup_error,
    suspend_time_counters,
    tick_suspend_counters,
    remove_suspended_card_from_exile,
    overload_creature_targets,
    overload_hits_each_creature,
    overload_opponent_indices,
    AnnounceCastManaOptions,
    CastManaModifiers,
    CastManaTiming,
    resolve_announce_cast_mana,
    resolve_overload_burn_damage,
    escape_mana_needed,
    extra_draw_from_kicker,
    resolve_burn_damage,
    flashback_mana_needed,
    has_escape,
    has_flashback,
    escape_payment_error,
    exile_for_escape_cost,
    kicked_counter_count,
    pump_with_kicker,
    resolve_cast_adjustments,
)
from engine.abilities.keywords.casting.cast_adjustments import CastAdjustmentInput
from engine.abilities.keywords.actions import (
    ActionContext,
    has_connive,
    keyword_actions_in_oracle,
    resolve_spell_keyword_actions,
)
from engine.abilities.keywords.actions.tokens import connive
from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.evoke import mark_evoked_cast
from engine.abilities.keywords.other.register import register_permanent_other_keywords
from engine.game._hand_card import load_hand_card_for_action, run_with_hand_card
from engine.game.cast_announce_validate import (
    HandCastPlacement,
    PaidAnnounceCast,
    validate_announce_cast,
)
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.cards.oracle_parse import parse_draw, spell_category
from engine.core.game_object import (
    ActivatedAbilityOnStack,
    CardObject,
    SpellAlternateCast,
    SpellCastPayment,
    SpellOnStack,
    Target,
    spell_is_ephemeral_copy,
    spell_returns_to_hand_on_resolve,
)
from engine.core.game_object import TriggeredAbilityOnStack
from engine.core.zones import Zone
from engine.game.helpers import (
    CastAnnounceOptions,
    SpellCastContext,
    can_cast_now,
    require_card_info,
    resolve_ability_effect,
    spell_on_stack_from_context,
    target_player as first_target_player,
    target_uid,
    targets_from_request,
)
from engine.game.helpers import card_names, last_creature
from engine.game.runtime import GameRuntimeMixin


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
    if mods.mutate:
        detail = f"{detail} (mutate)"
    if mods.spree_modes:
        detail = f"{detail} (spree modes {list(mods.spree_modes)})"
    return detail


class SpellStackMixin(GameRuntimeMixin):
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
        )
        if val_err:
            return {**self.to_client(), "error": val_err}
        assert paid is not None
        mana_needed, life_cost = resolve_announce_cast_mana(
            card_info,
            AnnounceCastManaOptions(
                modifiers=CastManaModifiers(
                    kicker_times=paid.modifiers.kicker_times,
                    entwined=paid.modifiers.entwined,
                    overloaded=paid.modifiers.overloaded,
                    bestow_target_uid=opts.modifiers.targeting.bestow_target_uid,
                    replicate_times=paid.modifiers.replicate_times,
                    paid_buyback=paid.modifiers.buyback,
                    cast_for_emerge=paid.modifiers.emerge,
                    cast_for_evoke=paid.modifiers.evoke,
                    cast_for_mutate=paid.modifiers.mutate,
                    mutate_target_uid=opts.modifiers.targeting.mutate_target_uid,
                    spree_mode_indices=paid.modifiers.spree_modes,
                ),
                timing=CastManaTiming(
                    cast_for_miracle=paid.modifiers.miracle,
                    cast_for_freerunning=paid.modifiers.freerunning,
                    freerunning_available=self.state.players[0].combat_damage_dealt_this_turn,
                ),
            ),
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
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        self.state.players[0].spells_cast_this_turn += 1
        if life_cost:
            self.state.players[0].life -= life_cost
            self._log("player", "phyrexian", f"Paid {life_cost} life for {card_info.name}")
        sacrificed_name = ""
        if paid.emerge_sacrifice_id is not None:
            sacrificed = sacrifice_for_emerge(
                self.state.zones,
                self.state,
                paid.emerge_sacrifice_id,
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
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        self.state.players[0].spells_cast_this_turn += 1
        if life_cost:
            self.state.players[0].life -= life_cost
            self._log("player", "phyrexian", f"Paid {life_cost} life for {card_info.name}")
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=request.target_uid_str,
            target_player_idx=request.target_player_idx,
            context=SpellCastContext(alternate=SpellAlternateCast(madness=True)),
        )
        self._log("player", "madness", f"{card_info.name} on stack")
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if request.auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

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
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        if life_cost:
            self.state.players[0].life -= life_cost
            self._log("player", "phyrexian", f"Paid {life_cost} life for {card_info.name}")
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

    def _announce_flashback_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Pay flashback cost and cast a card from the graveyard."""
        card = self._zones(0).graveyard[graveyard_idx]
        if not isinstance(card, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(card)
        if not has_flashback(card_info):
            return {**self.to_client(), "error": f"{card_info.name} does not have flashback"}
        if not can_cast_via_flashback(
            card_info,
            self.phase,
            self.state.stack.is_empty,
        ):
            return {**self.to_client(), "error": "Cannot cast flashback now"}
        mana_needed = flashback_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        self.state.players[0].spells_cast_this_turn += 1
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=target_uid_str,
            target_player_idx=target_player_idx,
            context=SpellCastContext(
                alternate=SpellAlternateCast(flashback=True),
                from_graveyard=True,
            ),
        )
        self._log("player", "flashback", f"{card_info.name} on stack")
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

    def _announce_aftermath_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Pay mana and cast an aftermath card from the graveyard."""
        card = self._zones(0).graveyard[graveyard_idx]
        if not isinstance(card, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(card)
        if not has_aftermath(card_info):
            return {**self.to_client(), "error": f"{card_info.name} does not have aftermath"}
        if not can_cast_aftermath(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot cast aftermath now"}
        mana_needed, life_cost = aftermath_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        self.state.players[0].spells_cast_this_turn += 1
        if life_cost:
            self.state.players[0].life -= life_cost
            self._log("player", "phyrexian", f"Paid {life_cost} life for {card_info.name}")
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=target_uid_str,
            target_player_idx=target_player_idx,
            context=SpellCastContext(
                alternate=SpellAlternateCast(aftermath=True),
                from_graveyard=True,
            ),
        )
        self._log("player", "aftermath", f"{card_info.name} on stack")
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

    def _announce_escape_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
        escape_exile_indices: list[int] | None = None,
    ) -> dict:
        """Pay escape costs and cast a card from the graveyard."""
        card = self._zones(0).graveyard[graveyard_idx]
        if not isinstance(card, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(card)
        if not has_escape(card_info):
            return {**self.to_client(), "error": f"{card_info.name} does not have escape"}
        if not can_cast_via_escape(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot cast escape now"}
        exile_err = escape_payment_error(
            self.state.zones,
            0,
            graveyard_idx,
            escape_exile_indices or [],
            card_info,
        )
        if exile_err:
            return {**self.to_client(), "error": exile_err}
        mana_needed = escape_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        exiled = exile_for_escape_cost(
            self.state.zones,
            0,
            escape_exile_indices or [],
            card_info,
        )
        self.state.players[0].spells_cast_this_turn += 1
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=target_uid_str,
            target_player_idx=target_player_idx,
            context=SpellCastContext(
                alternate=SpellAlternateCast(escape=True),
                from_graveyard=True,
            ),
        )
        detail = f"{card_info.name} on stack"
        if exiled:
            detail = f"{detail} (escape, exiled {len(exiled)} for cost)"
        self._log("player", "escape", detail)
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

    def _announce_jump_start_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
        discard_hand_idx: int | None = None,
    ) -> dict:
        """Discard a card, pay jump-start cost, and cast from the graveyard."""
        card = self._zones(0).graveyard[graveyard_idx]
        if not isinstance(card, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(card)
        if not has_jump_start(card_info):
            return {**self.to_client(), "error": f"{card_info.name} does not have jump-start"}
        if not can_cast_via_jump_start(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot cast jump-start now"}
        discard_err = jump_start_discard_error(self.state.zones, 0, discard_hand_idx)
        if discard_err:
            return {**self.to_client(), "error": discard_err}
        mana_needed = jump_start_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        assert discard_hand_idx is not None
        discarded = discard_for_jump_start(self.state.zones, 0, discard_hand_idx)
        self.state.players[0].spells_cast_this_turn += 1
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=target_uid_str,
            target_player_idx=target_player_idx,
            context=SpellCastContext(
                alternate=SpellAlternateCast(jump_start=True),
                from_graveyard=True,
            ),
        )
        discard_info = require_card_info(discarded)
        self._log(
            "player",
            "jump-start",
            f"{card_info.name} on stack (discarded {discard_info.name})",
        )
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

    def _announce_retrace_cast(
        self,
        graveyard_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
        discard_hand_idx: int | None = None,
    ) -> dict:
        """Discard a land, pay the spell's mana cost, and cast from the graveyard."""
        card = self._zones(0).graveyard[graveyard_idx]
        if not isinstance(card, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(card)
        if not has_retrace(card_info):
            return {**self.to_client(), "error": f"{card_info.name} does not have retrace"}
        if not can_cast_via_retrace(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot cast retrace now"}
        discard_err = retrace_land_discard_error(self.state.zones, 0, discard_hand_idx)
        if discard_err:
            return {**self.to_client(), "error": discard_err}
        mana_needed = retrace_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        assert discard_hand_idx is not None
        life_cost = retrace_life_cost(card_info)
        if life_cost:
            self.state.players[0].life -= life_cost
            self._log("player", "phyrexian", f"Paid {life_cost} life for {card_info.name}")
        discarded = discard_land_for_retrace(self.state.zones, 0, discard_hand_idx)
        self.state.players[0].spells_cast_this_turn += 1
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=target_uid_str,
            target_player_idx=target_player_idx,
            context=SpellCastContext(
                alternate=SpellAlternateCast(retrace=True),
                from_graveyard=True,
            ),
        )
        discard_info = require_card_info(discarded)
        self._log(
            "player",
            "retrace",
            f"{card_info.name} on stack (discarded {discard_info.name})",
        )
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

    def action_foretell(self, hand_idx: int) -> dict:
        """Exile a card from hand for its foretell cost during a main phase."""
        card = self._zones(0).hand[hand_idx]
        if not isinstance(card, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(card)
        setup_err = foretell_setup_error(
            self.state.zones,
            0,
            hand_idx,
            card_info,
            self.phase,
            self.state.stack.is_empty,
        )
        if setup_err:
            return {**self.to_client(), "error": setup_err}
        if not self._tap_lands_for_mana(0, FORETELL_SETUP_MANA):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {FORETELL_SETUP_MANA})"
                ),
            }
        exile_for_foretell(self.state.zones, 0, hand_idx)
        self._log("player", "foretell", f"Foretold {card_info.name}")
        return self.to_client()

    def _announce_cast_foretell(
        self,
        exile_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Cast a foretold card from exile for its foretell cost."""
        exile = self._zones(0).exile
        if exile_idx < 0 or exile_idx >= len(exile):
            return {**self.to_client(), "error": f"Exile index {exile_idx} out of range"}
        preview = exile[exile_idx]
        if not isinstance(preview, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(preview)
        cast_err = foretold_cast_error(
            self.state.zones,
            0,
            exile_idx,
            card_info,
            self.phase,
            self.state.stack.is_empty,
        )
        if cast_err:
            return {**self.to_client(), "error": cast_err}
        mana_needed, life_cost = foretell_cast_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        card = cast_from_foretell_exile(self.state.zones, 0, exile_idx)
        if life_cost:
            self.state.players[0].life -= life_cost
            self._log("player", "phyrexian", f"Paid {life_cost} life for {card_info.name}")
        self.state.players[0].spells_cast_this_turn += 1
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=target_uid_str,
            target_player_idx=target_player_idx,
            context=SpellCastContext(
                alternate=SpellAlternateCast(foretell=True),
                from_exile=True,
            ),
        )
        self._log("player", "cast", f"{card_info.name} on stack (foretell)")
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

    def action_plot(self, hand_idx: int) -> dict:
        """Exile a sorcery from hand to plot it during a main phase."""
        card = self._zones(0).hand[hand_idx]
        if not isinstance(card, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(card)
        setup_err = plot_setup_error(
            self.state.zones,
            0,
            hand_idx,
            card_info,
            self.phase,
            self.state.stack.is_empty,
        )
        if setup_err:
            return {**self.to_client(), "error": setup_err}
        exile_for_plot(self.state.zones, 0, hand_idx)
        self._log("player", "plot", f"Plotted {card_info.name}")
        return self.to_client()

    def _announce_cast_plot(
        self,
        exile_idx: int,
        target_uid_str: str | None,
        target_player_idx: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Cast a plotted sorcery from exile without paying mana."""
        exile = self._zones(0).exile
        if exile_idx < 0 or exile_idx >= len(exile):
            return {**self.to_client(), "error": f"Exile index {exile_idx} out of range"}
        preview = exile[exile_idx]
        if not isinstance(preview, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(preview)
        cast_err = plotted_cast_error(
            self.state.zones,
            0,
            exile_idx,
            card_info,
            self.phase,
            self.state.stack.is_empty,
        )
        if cast_err:
            return {**self.to_client(), "error": cast_err}
        card = cast_from_plot_exile(self.state.zones, 0, exile_idx)
        self.state.players[0].spells_cast_this_turn += 1
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=target_uid_str,
            target_player_idx=target_player_idx,
            context=SpellCastContext(
                alternate=SpellAlternateCast(plot=True),
                from_exile=True,
            ),
        )
        self._log("player", "cast", f"{card_info.name} on stack (plot)")
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

    def _put_spell_on_stack(
        self,
        player_idx: int,
        card: CardObject,
        target_uid_str: str | None,
        target_player_idx: int | None,
        context: SpellCastContext | None = None,
    ) -> list[Target]:
        """Move a cast spell onto the stack."""
        opts = context or SpellCastContext()
        targets = targets_from_request(target_uid_str, target_player_idx)
        if opts.from_graveyard:
            self.state.zones.cast_from_graveyard(card, player_idx)
        elif not opts.from_exile:
            self.state.zones.play_from_hand(card, player_idx)
        self.state.stack.push(spell_on_stack_from_context(
            player_idx,
            card,
            targets,
            opts,
        ))
        actor = "player" if player_idx == 0 else "opponent"
        for detail in apply_post_cast_modifiers(self.state, player_idx, card, targets, opts):
            self._log(actor, "storm" if "storm" in detail else "cascade", detail)
        self.state.turn.action_taken()
        return targets

    def _spell_keyword_action_detail(
        self,
        spell: SpellOnStack,
        *,
        skip_actions: frozenset[str] = frozenset(),
    ) -> str:
        """Apply keyword actions from oracle text after the primary spell effect."""
        card = spell.source
        if card is None or card.card_info is None:
            return ""
        second_uid = None
        if len(spell.targets) >= 2:
            second_uid = target_uid([spell.targets[1]])
        detail = resolve_spell_keyword_actions(ActionContext(
            zones=self.state.zones,
            game=self.state,
            controller_idx=spell.controller_idx,
            oracle_text=card.card_info.oracle_text or '',
            target_creature_uid=target_uid(spell.targets),
            second_creature_uid=second_uid,
            draw_fn=self._draw_cards,
            skip_actions=skip_actions,
        ))
        if detail:
            self.state.check_sbas()
        return detail

    def _resolve_top_of_stack(self) -> str:
        """Resolve the top stack object and apply its simple Phase B effect."""
        result = self.state.stack.resolve_top(self.state.zones, self.state)
        if result.obj is None:
            return ""
        if result.fizzled:
            source = getattr(result.obj, "source", None)
            name = require_card_info(source).name if isinstance(source, CardObject) else "Object"
            return f"{name} fizzled"
        obj = result.obj
        if isinstance(obj, SpellOnStack) and obj.source is not None:
            return self._apply_spell(obj)
        if isinstance(obj, (TriggeredAbilityOnStack, ActivatedAbilityOnStack)):
            return resolve_ability_effect(obj, self.state)
        return "Resolved ability"

    def _apply_spell(self, spell: SpellOnStack) -> str:
        """Apply a resolved spell's effect."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        if spell.modes and has_spree(card_info):
            return self._resolve_spree_spell(spell)
        category = spell_category(card_info)
        dispatch = {
            "creature": self._resolve_creature_spell,
            "burn": self._resolve_burn,
            "pump": self._resolve_pump,
            "removal": self._resolve_removal,
            "draw": self._resolve_draw,
        }
        handler = dispatch.get(category)
        skip_actions: frozenset[str] = frozenset()
        if category == 'draw' and has_connive(card_info.oracle_text or ''):
            skip_actions = frozenset({'Connive'})
        if handler is not None:
            primary = handler(spell)
            extras = self._spell_keyword_action_detail(spell, skip_actions=skip_actions)
            if extras:
                return f"{primary}; {extras}"
            return primary
        if keyword_actions_in_oracle(card_info.oracle_text):
            extras = self._spell_keyword_action_detail(spell)
            if extras:
                self._relocate_resolved_spell(spell, card)
                return f"{card_info.name}: {extras}"
        self._relocate_resolved_spell(spell, card)
        return f"Cast {card_info.name}"

    def _resolve_spree_spell(self, spell: SpellOnStack) -> str:
        """Resolve a spree spell by applying each chosen mode."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        options = spree_modes(card_info)
        controller_idx = spell.controller_idx
        parts: list[str] = []
        for idx in spell.modes:
            if idx >= len(options):
                continue
            effect = options[idx].effect
            draw_count = spree_mode_draw(effect)
            if draw_count:
                drawn = self._draw_cards(controller_idx, draw_count)
                parts.append(f"drew {card_names(drawn) or 'no cards'}")
            damage = spree_mode_damage(effect)
            if damage:
                target_uid_val = target_uid(spell.targets)
                target_player_idx = first_target_player(spell.targets)
                victim_idx = (
                    target_player_idx
                    if target_player_idx is not None
                    else 1 - controller_idx
                )
                if target_uid_val is None:
                    self._deal_damage_to_player(victim_idx, damage)
                    parts.append(f"dealt {damage} damage")
                else:
                    target = self._find_permanent(target_uid_val)
                    if target is not None:
                        target.damage_marked += damage
                        parts.append(f"dealt {damage} to {target.name}")
            if spree_mode_is_destroy(effect):
                target_uid_val = target_uid(spell.targets)
                target = self._find_permanent(target_uid_val)
                if target is not None:
                    self.state.zones.leave_battlefield(
                        target,
                        Zone.GRAVEYARD,
                        'destroy',
                        self.state,
                    )
                    parts.append(f"destroyed {target.name}")
        if spell.modes:
            self.state.check_sbas()
        self._relocate_resolved_spell(spell, card)
        detail = ", ".join(parts) if parts else "no effect"
        return f"{card_info.name} spree ({detail})"

    def _resolve_creature_spell(self, spell: SpellOnStack) -> str:
        """Resolve a creature spell onto the battlefield."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        if spell_is_ephemeral_copy(spell):
            return f"Storm copy of {card_info.name} (creature copies not modeled)"
        if spell_returns_to_hand_on_resolve(spell):
            self._zones(card.owner_idx).hand.append(card)
            return f"{card_info.name} returned to hand (buyback)"
        if spell.payment.mutate:
            host_id = target_uid(spell.targets)
            if host_id is not None:
                host = self._find_permanent(host_id)
                if host is not None:
                    bonus = mutate_bonus_counters(card_info)
                    host.counters['+1/+1'] = host.counters.get('+1/+1', 0) + bonus
                    self._move_card_to_graveyard(card)
                    return f"Mutated {card_info.name} onto {host.name} (+{bonus}/+{bonus})"
            self._move_card_to_graveyard(card)
            return f"Cast {card_info.name} (mutate target not found)"
        permanent = self.state.zones.enter_battlefield(
            card,
            spell.controller_idx,
            "resolve",
        )
        if spell.payment.bestow:
            host_id = target_uid(spell.targets)
            if host_id is not None:
                permanent.attached_to = int(host_id)
                host = self._find_permanent(host_id)
                host_name = host.name if host is not None else "creature"
                detail = f"Bestowed {card_info.name} on {host_name}"
                counters = kicked_counter_count(card_info, spell.payment.kicker_times)
                if counters:
                    permanent.counters["+1/+1"] = (
                        permanent.counters.get("+1/+1", 0) + counters
                    )
                self._register_permanent_triggers(permanent)
                return detail
        counters = kicked_counter_count(card_info, spell.payment.kicker_times)
        if counters:
            permanent.counters["+1/+1"] = permanent.counters.get("+1/+1", 0) + counters
        if spell.payment.evoke:
            mark_evoked_cast(permanent)
        self._register_permanent_triggers(permanent)
        detail = f"Cast creature {card_info.name}"
        if counters:
            detail = f"{detail} with {counters} +1/+1 counter(s)"
        return detail

    def _resolve_burn(self, spell: SpellOnStack) -> str:
        """Resolve a burn spell."""
        card = spell.source
        assert card is not None
        targets = spell.targets
        card_info = require_card_info(card)
        controller_idx = spell.controller_idx
        if spell.payment.overloaded:
            damage = resolve_overload_burn_damage(card_info, spell.payment.kicker_times)
            self._relocate_resolved_spell(spell, card)
            if overload_hits_each_creature(card_info):
                for perm in overload_creature_targets(self.state.zones.battlefield):
                    perm.damage_marked += damage
                self.state.check_sbas()
                return f"{card_info.name} dealt {damage} damage to each creature"
            for idx in overload_opponent_indices(controller_idx):
                self._deal_damage_to_player(idx, damage)
            return f"{card_info.name} dealt {damage} damage to each opponent"
        damage = resolve_burn_damage(card_info, spell.payment.entwined, spell.payment.kicker_times)
        extra_draw = entwined_extra_draw(card_info, spell.payment.entwined)
        self._relocate_resolved_spell(spell, card)
        target_uid_val = target_uid(targets)
        target_player_idx = first_target_player(targets)
        default_player = 1 - controller_idx
        if target_uid_val is None:
            victim_idx = (
                target_player_idx if target_player_idx is not None else default_player
            )
            self._deal_damage_to_player(victim_idx, damage)
            label = "opponent" if victim_idx == 1 else "you"
            detail = f"{card_info.name} dealt {damage} damage to {label}"
            if extra_draw:
                drawn = self._draw_cards(controller_idx, extra_draw)
                detail = f"{detail} and drew {card_names(drawn) or 'no cards'}"
            return detail
        target = self._find_permanent(target_uid_val)
        if target is None:
            return f"Cast {card_info.name} (no valid target)"
        target.damage_marked += damage
        self.state.check_sbas()
        return f"{card_info.name} dealt {damage} damage to {target.name}"

    def _resolve_pump(self, spell: SpellOnStack) -> str:
        """Resolve a pump spell."""
        card = spell.source
        assert card is not None
        targets = spell.targets
        card_info = require_card_info(card)
        controller_idx = spell.controller_idx
        power, toughness = pump_with_kicker(card_info, spell.payment.kicker_times)
        target_uid_val = target_uid(targets)
        target = (
            self._find_permanent(target_uid_val)
            or last_creature(self._permanents(controller_idx))
        )
        self._relocate_resolved_spell(spell, card)
        if target is None:
            return f"Cast {card_info.name} (no target)"
        target.counters["+1/+1"] = target.counters.get("+1/+1", 0) + max(power, toughness)
        return f"{card_info.name} pumped {target.name}"

    def _resolve_removal(self, spell: SpellOnStack) -> str:
        """Resolve a destruction or exile spell."""
        card = spell.source
        assert card is not None
        targets = spell.targets
        card_info = require_card_info(card)
        self._relocate_resolved_spell(spell, card)
        target_uid_val = target_uid(targets)
        target = self._find_permanent(target_uid_val)
        if target is None:
            return f"Cast {card_info.name} (target not found)"
        self.state.zones.leave_battlefield(target, Zone.GRAVEYARD, "destroy", self.state)
        return f"{card_info.name} destroyed {target.name}"

    def _resolve_draw(self, spell: SpellOnStack) -> str:
        """Resolve a draw spell."""
        card = spell.source
        assert card is not None
        controller_idx = spell.controller_idx
        card_info = require_card_info(card)
        oracle = card_info.oracle_text or ''
        if has_connive(oracle):
            detail = connive(self.state.zones, controller_idx, oracle, self._draw_cards)
            self._relocate_resolved_spell(spell, card)
            return f"{card_info.name} {detail}"
        count = (parse_draw(oracle) or 1) + extra_draw_from_kicker(
            card_info,
            spell.payment.kicker_times,
        )
        drawn = self._draw_cards(controller_idx, count)
        self._relocate_resolved_spell(spell, card)
        return f"{card_info.name} drew {card_names(drawn) or 'no cards'}"

    def _register_permanent_triggers(self, permanent) -> None:
        """Register parsed triggered abilities from a newly resolved permanent."""
        for detail in apply_etb_other_abilities(self.state, permanent):
            self._log("rules", "ability_other", detail)
        register_permanent_other_keywords(permanent, self.state.trigger_registry)
        register_permanent_ability_words(permanent, self.state.trigger_registry)

    def _deal_damage_to_player(self, player_idx: int, amount: int) -> None:
        """Deal damage to a player and mark Raid-related flags."""
        if amount <= 0:
            return
        self.state.players[player_idx].life -= amount
        self.state.mark_player_was_dealt_damage(player_idx)
