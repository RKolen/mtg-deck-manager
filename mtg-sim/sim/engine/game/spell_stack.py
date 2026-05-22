"""Casting and stack resolution for InteractiveGame."""

from __future__ import annotations

from engine.abilities.keywords.casting import (
    aftermath_mana_needed,
    normalize_buyback,
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
    bestow_host_error,
    entwined_extra_draw,
    normalize_bestow,
    normalize_miracle_cast,
    normalize_overloaded,
    normalize_replicate_times,
    overload_creature_targets,
    overload_hits_each_creature,
    overload_opponent_indices,
    AnnounceCastManaOptions,
    resolve_announce_cast_mana,
    resolve_overload_burn_damage,
    escape_mana_needed,
    extra_draw_from_kicker,
    normalize_entwined,
    resolve_burn_damage,
    flashback_mana_needed,
    has_escape,
    has_flashback,
    escape_payment_error,
    exile_for_escape_cost,
    kicked_counter_count,
    normalize_kicker_times,
    pump_with_kicker,
    resolve_cast_adjustments,
)
from engine.abilities.keywords.casting.cast_adjustments import CastAdjustmentInput
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.cards.oracle_parse import parse_draw, parse_token_blueprint, spell_category
from engine.core.game_object import (
    ActivatedAbilityOnStack,
    CardObject,
    SpellOnStack,
    Target,
    spell_is_ephemeral_copy,
    spell_returns_to_hand_on_resolve,
)
from engine.core.game_object import TriggeredAbilityOnStack
from engine.core.zones import Zone
from engine.game.helpers import (
    CastAnnounceOptions,
    CreateTokenEffect,
    SpellCastContext,
    can_cast_now,
    require_card_info,
    resolve_ability_effect,
    target_player as first_target_player,
    target_uid,
    targets_from_request,
)
from engine.game.helpers import card_names, last_creature
from engine.game.runtime import GameRuntimeMixin
from engine.rules.triggers import TriggerKey, is_noncreature_nonland_spell_cast
from engine.rules.triggers import is_spell_targeting_source


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
        card = self._zones(0).hand[hand_idx]
        if not isinstance(card, CardObject):
            return {**self.to_client(), "error": "Invalid card"}
        card_info = require_card_info(card)
        assert can_cast_now(card_info, self.phase, self.state.stack.is_empty)
        paid_kicker = normalize_kicker_times(card_info, opts.kicker_times)
        if opts.kicker_times > 0 and paid_kicker == 0:
            return {**self.to_client(), "error": f"{card_info.name} does not have kicker"}
        paid_entwined = normalize_entwined(card_info, opts.entwined)
        if opts.entwined and not paid_entwined:
            return {**self.to_client(), "error": f"{card_info.name} does not have entwine"}
        paid_overloaded = normalize_overloaded(card_info, opts.overloaded)
        if opts.overloaded and not paid_overloaded:
            return {**self.to_client(), "error": f"{card_info.name} does not have overload"}
        paid_bestow = normalize_bestow(card_info, opts.bestow_target_uid)
        if opts.bestow_target_uid and not paid_bestow:
            return {**self.to_client(), "error": f"{card_info.name} does not have bestow"}
        host_err = bestow_host_error(self.state.zones, 0, opts.bestow_target_uid)
        if host_err:
            return {**self.to_client(), "error": host_err}
        paid_miracle = normalize_miracle_cast(card_info, opts.cast_for_miracle)
        if opts.cast_for_miracle and not paid_miracle:
            return {**self.to_client(), "error": f"{card_info.name} does not have miracle"}
        paid_replicate = normalize_replicate_times(card_info, opts.replicate_times)
        if opts.replicate_times > 0 and paid_replicate == 0:
            return {**self.to_client(), "error": f"{card_info.name} does not have replicate"}
        paid_buyback = normalize_buyback(card_info, opts.paid_buyback)
        if opts.paid_buyback and not paid_buyback:
            return {**self.to_client(), "error": f"{card_info.name} does not have buyback"}
        cast_target_uid = opts.bestow_target_uid or target_uid_str
        mana_needed, life_cost = resolve_announce_cast_mana(
            card_info,
            AnnounceCastManaOptions(
                kicker_times=paid_kicker,
                entwined=paid_entwined,
                overloaded=paid_overloaded,
                bestow_target_uid=opts.bestow_target_uid,
                cast_for_miracle=paid_miracle,
                replicate_times=paid_replicate,
                paid_buyback=paid_buyback,
            ),
        )
        adjustments = resolve_cast_adjustments(
            card_info,
            mana_needed,
            CastAdjustmentInput(
                convoke_creature_ids=opts.convoke_creature_ids,
                delve_graveyard_indices=opts.delve_graveyard_indices,
                improvise_artifact_ids=opts.improvise_artifact_ids,
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
        targets = self._put_spell_on_stack(
            player_idx=0,
            card=card,
            target_uid_str=cast_target_uid,
            target_player_idx=target_player_idx,
            context=SpellCastContext(
                kicker_times=paid_kicker,
                entwined=paid_entwined,
                overloaded=paid_overloaded,
                cast_via_bestow=paid_bestow,
                cast_for_miracle=paid_miracle,
                replicate_times=paid_replicate,
                paid_buyback=paid_buyback,
            ),
        )
        cast_detail = f"{card_info.name} on stack"
        if paid_miracle:
            cast_detail = f"{cast_detail} (miracle)"
        if paid_replicate:
            cast_detail = f"{cast_detail} (replicate x{paid_replicate})"
        if paid_overloaded:
            cast_detail = f"{cast_detail} (overloaded)"
        if paid_bestow:
            cast_detail = f"{cast_detail} (bestow)"
        if paid_entwined:
            cast_detail = f"{cast_detail} (entwined)"
        if paid_kicker:
            cast_detail = f"{cast_detail} (kicked x{paid_kicker})"
        if paid_buyback:
            cast_detail = f"{cast_detail} (buyback)"
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
        self._log("player", "cast", cast_detail)
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

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
            context=SpellCastContext(cast_via_flashback=True, from_graveyard=True),
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
            context=SpellCastContext(cast_via_aftermath=True, from_graveyard=True),
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
            context=SpellCastContext(cast_via_escape=True, from_graveyard=True),
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
            context=SpellCastContext(cast_via_jump_start=True, from_graveyard=True),
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
            context=SpellCastContext(cast_via_retrace=True, from_graveyard=True),
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
        else:
            self.state.zones.play_from_hand(card, player_idx)
        self.state.stack.push(SpellOnStack(
            controller_idx=player_idx,
            owner_idx=card.owner_idx,
            source=card,
            targets=targets,
            cast_via_flashback=opts.cast_via_flashback,
            cast_via_escape=opts.cast_via_escape,
            cast_via_jump_start=opts.cast_via_jump_start,
            cast_via_retrace=opts.cast_via_retrace,
            cast_via_aftermath=opts.cast_via_aftermath,
            kicker_times=opts.kicker_times,
            entwined=opts.entwined,
            overloaded=opts.overloaded,
            cast_via_bestow=opts.cast_via_bestow,
            paid_buyback=opts.paid_buyback,
        ))
        actor = "player" if player_idx == 0 else "opponent"
        for detail in apply_post_cast_modifiers(self, player_idx, card, targets, opts):
            self._log(actor, "storm" if "storm" in detail else "cascade", detail)
        self.state.turn.action_taken()
        return targets

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
        category = spell_category(card_info)
        dispatch = {
            "creature": self._resolve_creature_spell,
            "burn": self._resolve_burn,
            "pump": self._resolve_pump,
            "removal": self._resolve_removal,
            "draw": self._resolve_draw,
        }
        handler = dispatch.get(category)
        if handler is not None:
            return handler(spell)
        self._relocate_resolved_spell(spell, card)
        return f"Cast {card_info.name}"

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
        permanent = self.state.zones.enter_battlefield(
            card,
            spell.controller_idx,
            "resolve",
        )
        if spell.cast_via_bestow:
            host_id = target_uid(spell.targets)
            if host_id is not None:
                permanent.attached_to = int(host_id)
                host = self._find_permanent(host_id)
                host_name = host.name if host is not None else "creature"
                detail = f"Bestowed {card_info.name} on {host_name}"
                counters = kicked_counter_count(card_info, spell.kicker_times)
                if counters:
                    permanent.counters["+1/+1"] = (
                        permanent.counters.get("+1/+1", 0) + counters
                    )
                self._register_permanent_triggers(permanent)
                return detail
        counters = kicked_counter_count(card_info, spell.kicker_times)
        if counters:
            permanent.counters["+1/+1"] = permanent.counters.get("+1/+1", 0) + counters
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
        if spell.overloaded:
            damage = resolve_overload_burn_damage(card_info, spell.kicker_times)
            self._relocate_resolved_spell(spell, card)
            if overload_hits_each_creature(card_info):
                for perm in overload_creature_targets(self.state.zones.battlefield):
                    perm.damage_marked += damage
                self.state.check_sbas()
                return f"{card_info.name} dealt {damage} damage to each creature"
            for idx in overload_opponent_indices(controller_idx):
                self.state.players[idx].life -= damage
            return f"{card_info.name} dealt {damage} damage to each opponent"
        damage = resolve_burn_damage(card_info, spell.entwined, spell.kicker_times)
        extra_draw = entwined_extra_draw(card_info, spell.entwined)
        self._relocate_resolved_spell(spell, card)
        target_uid_val = target_uid(targets)
        target_player_idx = first_target_player(targets)
        default_player = 1 - controller_idx
        if target_uid_val is None:
            victim_idx = (
                target_player_idx if target_player_idx is not None else default_player
            )
            self.state.players[victim_idx].life -= damage
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
        power, toughness = pump_with_kicker(card_info, spell.kicker_times)
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
        count = (parse_draw(card_info.oracle_text or "") or 1) + extra_draw_from_kicker(
            card_info,
            spell.kicker_times,
        )
        drawn = self._draw_cards(controller_idx, count)
        self._relocate_resolved_spell(spell, card)
        return f"{card_info.name} drew {card_names(drawn) or 'no cards'}"

    def _register_permanent_triggers(self, permanent) -> None:
        """Register parsed triggered abilities from a newly resolved permanent."""
        oracle = permanent.oracle_text.lower()
        if "heroic" in oracle:
            blueprint = parse_token_blueprint(permanent.oracle_text)
            if blueprint is not None:
                self.state.trigger_registry.register(
                    permanent,
                    TriggerKey.SPELL_CAST,
                    is_spell_targeting_source,
                    effect=CreateTokenEffect(blueprint),
                )
        if "prowess" in oracle:
            self.state.trigger_registry.register(
                permanent,
                TriggerKey.SPELL_CAST,
                is_noncreature_nonland_spell_cast,
            )
