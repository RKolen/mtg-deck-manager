"""Casting and stack resolution for InteractiveGame."""

from __future__ import annotations

from engine.abilities.keywords.casting import (
    can_cast_via_escape,
    can_cast_via_flashback,
    can_cast_via_jump_start,
    discard_for_jump_start,
    has_jump_start,
    jump_start_discard_error,
    jump_start_mana_needed,
    cast_mana_needed,
    escape_mana_needed,
    extra_draw_from_kicker,
    flashback_mana_needed,
    has_escape,
    has_flashback,
    escape_payment_error,
    exile_for_escape_cost,
    has_kicker,
    kicked_counter_count,
    normalize_kicker_times,
    pump_with_kicker,
    resolve_cast_adjustments,
    spell_damage,
)
from engine.abilities.keywords.casting.cast_adjustments import CastAdjustmentInput
from engine.game.cast_modifiers import apply_post_cast_modifiers
from engine.cards.oracle_parse import parse_draw, parse_token_blueprint, spell_category
from engine.core.game_object import ActivatedAbilityOnStack, CardObject, SpellOnStack, Target
from engine.core.game_object import TriggeredAbilityOnStack
from engine.core.zones import Zone
from engine.game.helpers import (
    CastAnnounceOptions,
    CreateTokenEffect,
    SpellCastContext,
    can_cast_now,
    payment_requirements,
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
        mana_needed, life_cost = (
            cast_mana_needed(card_info, paid_kicker)
            if has_kicker(card_info)
            else payment_requirements(card_info)
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
            target_uid_str=target_uid_str,
            target_player_idx=target_player_idx,
            context=SpellCastContext(kicker_times=paid_kicker),
        )
        cast_detail = f"{card_info.name} on stack"
        if paid_kicker:
            cast_detail = f"{card_info.name} on stack (kicked x{paid_kicker})"
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
            kicker_times=opts.kicker_times,
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
        if spell.is_storm_copy:
            return f"Storm copy of {card_info.name} (creature copies not modeled)"
        permanent = self.state.zones.enter_battlefield(
            card,
            spell.controller_idx,
            "resolve",
        )
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
        damage = spell_damage(card_info, spell.kicker_times)
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
            return f"{card_info.name} dealt {damage} damage to {label}"
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
