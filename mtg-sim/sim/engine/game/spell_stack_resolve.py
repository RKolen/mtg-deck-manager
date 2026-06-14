"""Spell resolution for SpellStackMixin."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities.keywords.actions import (
    ActionContext,
    has_connive,
    keyword_actions_in_oracle,
    resolve_spell_keyword_actions,
)
from engine.abilities.keywords.actions.resolve import _ActionExtras, _ActionTargets
from engine.abilities.keywords.actions.tokens import connive
from engine.abilities.keywords.ability_words import register_permanent_ability_words
from engine.abilities.keywords.casting import (
    entwined_extra_draw,
    extra_draw_from_kicker,
    has_spree,
    kicked_counter_count,
    mutate_bonus_counters,
    overload_creature_targets,
    overload_hits_each_creature,
    overload_opponent_indices,
    pump_with_kicker,
    resolve_burn_damage,
    resolve_overload_burn_damage,
    spree_mode_damage,
    spree_mode_draw,
    spree_mode_is_destroy,
    spree_modes,
)
from engine.abilities.keywords.casting.awaken import apply_awaken_on_resolve
from engine.abilities.keywords.casting.impending import apply_impending_on_resolve
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.evoke import mark_evoked_cast
from engine.abilities.keywords.other.register import register_permanent_other_keywords
from engine.cards.oracle_parse import parse_draw, spell_category
from engine.core.game_object import (
    ActivatedAbilityOnStack,
    CardObject,
    Permanent,
    SpellOnStack,
    TriggeredAbilityOnStack,
    spell_is_ephemeral_copy,
    spell_returns_to_hand_on_resolve,
)
from engine.core.zones import Zone
from engine.game.helpers import (
    card_names,
    last_creature,
    require_card_info,
    resolve_ability_effect,
    target_player as first_target_player,
    target_uid,
)
from engine.game.spell_stack_placement import SpellStackPlacementMixin


class SpellResolveMixin(SpellStackPlacementMixin):
    """Resolve spells and register permanent triggers."""

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
            targets=_ActionTargets(
                target_creature_uid=target_uid(spell.targets),
                second_creature_uid=second_uid,
            ),
            extras=_ActionExtras(
                draw_fn=self._draw_cards,
                skip_actions=skip_actions,
            ),
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
        if spell.casting.impending:
            detail = apply_impending_on_resolve(
                self.state.zones,
                spell.controller_idx,
                card,
            )
            if detail:
                self._register_permanent_triggers(self.state.zones.battlefield[-1])
                return detail
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
            awaken_detail = self._apply_awaken_on_resolve(spell)
            extras = self._spell_keyword_action_detail(spell, skip_actions=skip_actions)
            parts = [primary]
            if awaken_detail:
                parts.append(awaken_detail)
            if extras:
                parts.append(extras)
            if len(parts) > 1:
                return "; ".join(parts)
            return primary
        if keyword_actions_in_oracle(card_info.oracle_text):
            extras = self._spell_keyword_action_detail(spell)
            if extras:
                self._relocate_resolved_spell(spell, card)
                return f"{card_info.name}: {extras}"
        self._relocate_resolved_spell(spell, card)
        return f"Cast {card_info.name}"

    def _apply_awaken_on_resolve(self, spell: SpellOnStack) -> str | None:
        """Animate a land when awaken was paid."""
        card = spell.source
        if card is None or card.card_info is None or not spell.payment.awaken:
            return None
        return apply_awaken_on_resolve(
            self.state.zones,
            spell.controller_idx,
            card.card_info,
            spell.casting.awaken_land_hand_idx,
        )

    def _apply_spree_mode(
        self,
        effect: str,
        spell: SpellOnStack,
        parts: list[str],
    ) -> None:
        """Apply one spree mode effect and append a description to parts."""
        controller_idx = spell.controller_idx
        draw_count = spree_mode_draw(effect)
        if draw_count:
            drawn = self._draw_cards(controller_idx, draw_count)
            parts.append(f"drew {card_names(drawn) or 'no cards'}")
        damage = spree_mode_damage(effect)
        if damage:
            target_uid_val = target_uid(spell.targets)
            target_player_idx = first_target_player(spell.targets)
            victim_idx = (
                target_player_idx if target_player_idx is not None else 1 - controller_idx
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
                    target, Zone.GRAVEYARD, 'destroy', self.state,
                )
                parts.append(f"destroyed {target.name}")

    def _resolve_spree_spell(self, spell: SpellOnStack) -> str:
        """Resolve a spree spell by applying each chosen mode."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        options = spree_modes(card_info)
        parts: list[str] = []
        for idx in spell.modes:
            if idx < len(options):
                self._apply_spree_mode(options[idx].effect, spell, parts)
        if spell.modes:
            self.state.check_sbas()
        self._relocate_resolved_spell(spell, card)
        detail = ", ".join(parts) if parts else "no effect"
        return f"{card_info.name} spree ({detail})"

    def _apply_creature_counters(self, permanent: Permanent, spell: SpellOnStack) -> None:
        """Apply face-down state and keyword counters after a creature enters."""
        if spell.payment.evoke:
            mark_evoked_cast(permanent)
        if spell.alternate.disturb:
            permanent.counters['disturbed'] = 1
        if spell.payment.morph_face_down or spell.payment.disguise_face_down:
            permanent.face_down = True
        if spell.payment.dash:
            permanent.sick = False
            permanent.counters['dash'] = 1
        if spell.payment.blitz:
            permanent.sick = False
            permanent.counters['blitz'] = 1

    def _resolve_mutate_cast(
        self,
        card: CardObject,
        card_info: CardInfo,
        spell: SpellOnStack,
    ) -> str:
        """Resolve a mutate cast: merge with or discard the creature."""
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
            return self._resolve_mutate_cast(card, card_info, spell)
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
        self._apply_creature_counters(permanent, spell)
        self._register_permanent_triggers(permanent)
        detail = f"Cast creature {card_info.name}"
        if counters:
            detail = f"{detail} with {counters} +1/+1 counter(s)"
        return detail

    def _resolve_overload_burn(
        self, spell: SpellOnStack, card: CardObject, card_info: CardInfo
    ) -> str:
        """Resolve an overloaded burn spell."""
        damage = resolve_overload_burn_damage(card_info, spell.payment.kicker_times)
        self._relocate_resolved_spell(spell, card)
        if overload_hits_each_creature(card_info):
            for perm in overload_creature_targets(self.state.zones.battlefield):
                perm.damage_marked += damage
            self.state.check_sbas()
            return f"{card_info.name} dealt {damage} damage to each creature"
        for idx in overload_opponent_indices(spell.controller_idx):
            self._deal_damage_to_player(idx, damage)
        return f"{card_info.name} dealt {damage} damage to each opponent"

    def _resolve_burn(self, spell: SpellOnStack) -> str:
        """Resolve a burn spell."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        if spell.payment.overloaded:
            return self._resolve_overload_burn(spell, card, card_info)
        targets = spell.targets
        damage = resolve_burn_damage(card_info, spell.payment.entwined, spell.payment.kicker_times)
        extra_draw = entwined_extra_draw(card_info, spell.payment.entwined)
        self._relocate_resolved_spell(spell, card)
        target_uid_val = target_uid(targets)
        if target_uid_val is None:
            return self._resolve_burn_to_player(spell, card_info, damage, extra_draw)
        target = self._find_permanent(target_uid_val)
        if target is None:
            return f"Cast {card_info.name} (no valid target)"
        target.damage_marked += damage
        self.state.check_sbas()
        return f"{card_info.name} dealt {damage} damage to {target.name}"

    def _resolve_burn_to_player(
        self,
        spell: SpellOnStack,
        card_info: CardInfo,
        damage: int,
        extra_draw: int,
    ) -> str:
        """Resolve burn that has no creature target (deals to a player)."""
        controller_idx = spell.controller_idx
        target_player_idx = first_target_player(spell.targets)
        victim_idx = (
            target_player_idx if target_player_idx is not None else 1 - controller_idx
        )
        self._deal_damage_to_player(victim_idx, damage)
        label = "opponent" if victim_idx == 1 else "you"
        detail = f"{card_info.name} dealt {damage} damage to {label}"
        if extra_draw:
            drawn = self._draw_cards(controller_idx, extra_draw)
            detail = f"{detail} and drew {card_names(drawn) or 'no cards'}"
        return detail

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

    def _register_permanent_triggers(self, permanent: Permanent) -> None:
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
