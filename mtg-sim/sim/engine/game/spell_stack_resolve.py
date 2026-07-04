"""Spell resolution for SpellStackMixin."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.cards.permanent_entry import (
    apply_planeswalker_entry,
    attach_aura,
    is_artifact_permanent,
    is_aura,
    is_enchantment_permanent,
    is_planeswalker,
)
from engine.abilities.keywords.actions import (
    ActionContext,
    has_connive,
    keyword_actions_in_oracle,
    resolve_spell_keyword_actions,
)
from engine.abilities.keywords.actions.resolve import _ActionExtras, _ActionTargets
from engine.abilities.keywords.actions.tokens import connive
from engine.abilities.keywords.casting import (
    entwined_extra_draw,
    extra_draw_from_kicker,
    has_spree,
    has_tiered,
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
from engine.abilities.keywords.casting.more_than_meets_the_eye import apply_converted_on_etb
from engine.abilities.keywords.casting.prototype import apply_prototype_on_etb
from engine.abilities.keywords.casting.tiered import tiered_modes
from engine.abilities.keywords.casting.warp import apply_warp_on_resolve
from engine.abilities.keywords.casting.squad import apply_squad_on_etb
from engine.abilities.keywords.other.etb import apply_etb_other_abilities
from engine.abilities.keywords.other.evoke import mark_evoked_cast
from engine.cards.effect_context_factory import card_effect_context_from_spell
from engine.cards.oracle_parse import parse_draw, spell_category
from engine.cards.script_loader import resolve_scripted_spell
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
from engine.rules.modifiers import add_until_eot_pt_modifier
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

    def _resolve_scripted_spell(self, spell: SpellOnStack) -> str | None:
        """Apply a Phase G card script when the resolving spell has one."""
        card = spell.source
        if card is None:
            return None
        ctx = card_effect_context_from_spell(self.state, spell, self._draw_cards)
        detail = resolve_scripted_spell(ctx)
        if detail:
            self.state.check_sbas()
        return detail

    def _resolve_impending_spell(self, spell: SpellOnStack, card: CardObject) -> str | None:
        """Resolve an impending spell early, or None to continue."""
        if not spell.casting.impending:
            return None
        detail = apply_impending_on_resolve(
            self.state.zones,
            spell.controller_idx,
            card,
        )
        if not detail:
            return None
        self._register_permanent_triggers(self.state.zones.battlefield[-1])
        return detail

    def _resolve_mode_or_scripted_spell(
        self,
        spell: SpellOnStack,
        card: CardObject,
        card_info: CardInfo,
    ) -> str | None:
        """Resolve tiered, spree, or scripted spells; None to use category dispatch."""
        if spell.modes and has_tiered(card_info):
            return self._resolve_tiered_spell(spell)
        if spell.modes and has_spree(card_info):
            return self._resolve_spree_spell(spell)
        scripted = self._resolve_scripted_spell(spell)
        if scripted is None:
            return None
        self._relocate_resolved_spell(spell, card)
        return f"{card_info.name}: {scripted}"

    def _resolve_spell_category(
        self,
        spell: SpellOnStack,
        card_info: CardInfo,
        category: str,
    ) -> str | None:
        """Dispatch a spell by oracle category; None when unhandled."""
        dispatch = {
            "creature": self._resolve_creature_spell,
            "burn": self._resolve_burn,
            "pump": self._resolve_pump,
            "removal": self._resolve_removal,
            "draw": self._resolve_draw,
        }
        handler = dispatch.get(category)
        if handler is None:
            return None
        skip_actions: frozenset[str] = frozenset()
        if category == 'draw' and has_connive(card_info.oracle_text or ''):
            skip_actions = frozenset({'Connive'})
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

    def _apply_spell(self, spell: SpellOnStack) -> str:
        """Apply a resolved spell's effect."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        detail = (
            self._resolve_impending_spell(spell, card)
            or self._resolve_mode_or_scripted_spell(spell, card, card_info)
        )
        if detail is not None:
            return detail
        permanent_detail = self._resolve_typed_permanent_spell(spell, card_info)
        if permanent_detail is not None:
            return permanent_detail
        category = spell_category(card_info)
        resolved = self._resolve_spell_category(spell, card_info, category)
        if resolved is not None:
            return resolved
        if keyword_actions_in_oracle(card_info.oracle_text):
            extras = self._spell_keyword_action_detail(spell)
            if extras:
                self._relocate_resolved_spell(spell, card)
                return f"{card_info.name}: {extras}"
        self._relocate_resolved_spell(spell, card)
        return f"Cast {card_info.name}"

    def _resolve_typed_permanent_spell(
        self,
        spell: SpellOnStack,
        card_info: CardInfo,
    ) -> str | None:
        """Resolve planeswalker, aura, artifact, or enchantment spells onto the battlefield."""
        if is_planeswalker(card_info):
            return self._resolve_planeswalker_spell(spell)
        if is_aura(card_info):
            return self._resolve_aura_spell(spell)
        if is_artifact_permanent(card_info) or is_enchantment_permanent(card_info):
            return self._resolve_permanent_spell(spell)
        return None

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

    def _resolve_tiered_spell(self, spell: SpellOnStack) -> str:
        """Resolve a tiered spell by applying the chosen mode."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        options = tiered_modes(card_info)
        parts: list[str] = []
        if spell.modes:
            idx = spell.modes[0]
            if idx < len(options):
                self._apply_spree_mode(options[idx].effect, spell, parts)
            self.state.check_sbas()
        self._relocate_resolved_spell(spell, card)
        detail = ", ".join(parts) if parts else "no effect"
        return f"{card_info.name} tiered ({detail})"

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

    def _resolve_aura_spell(self, spell: SpellOnStack) -> str:
        """Resolve an Aura: enter the battlefield attached to its target."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        host_id = target_uid(spell.targets)
        host = self._find_permanent(host_id) if host_id is not None else None
        permanent = self.state.zones.enter_battlefield(
            card,
            spell.controller_idx,
            'resolve',
        )
        attach_detail = attach_aura(permanent, host)
        self._register_permanent_triggers(permanent)
        self.state.check_sbas()
        if attach_detail:
            return attach_detail
        self.state.zones.leave_battlefield(permanent, Zone.GRAVEYARD, 'aura_illegal', self.state)
        return f'{card_info.name} (no legal enchant target)'

    def _resolve_planeswalker_spell(self, spell: SpellOnStack) -> str:
        """Resolve a planeswalker spell onto the battlefield."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        permanent = self.state.zones.enter_battlefield(
            card,
            spell.controller_idx,
            'resolve',
        )
        loyalty = apply_planeswalker_entry(permanent)
        self._register_permanent_triggers(permanent)
        detail = f'Cast planeswalker {card_info.name}'
        if loyalty:
            detail = f'{detail} ({loyalty} loyalty)'
        return detail

    def _resolve_permanent_spell(self, spell: SpellOnStack) -> str:
        """Resolve an artifact or non-Aura enchantment onto the battlefield."""
        card = spell.source
        assert card is not None
        card_info = require_card_info(card)
        permanent = self.state.zones.enter_battlefield(
            card,
            spell.controller_idx,
            'resolve',
        )
        self._register_permanent_triggers(permanent)
        self.state.check_sbas()
        return f'Cast {card_info.name}'

    def _resolve_creature_etb(
        self,
        permanent: Permanent,
        spell: SpellOnStack,
        card_info: CardInfo,
        counters: int,
    ) -> str:
        """Apply ETB modifiers and counters after a normal creature resolve."""
        detail = f"Cast creature {card_info.name}"
        if spell.casting.converted:
            converted_detail = apply_converted_on_etb(permanent)
            if converted_detail:
                detail = converted_detail
        if spell.casting.prototype:
            proto_detail = apply_prototype_on_etb(permanent)
            if proto_detail:
                detail = proto_detail
        if spell.casting.warp:
            warp_detail = apply_warp_on_resolve(permanent)
            if warp_detail:
                detail = f"{detail}; {warp_detail}"
        self._apply_creature_counters(permanent, spell)
        squad_detail = apply_squad_on_etb(
            self.state.zones,
            permanent,
            spell.payment.squad_times,
        )
        if squad_detail:
            detail = f"{detail}; {squad_detail}"
        self._register_permanent_triggers(permanent)
        if counters:
            detail = f"{detail} with {counters} +1/+1 counter(s)"
        return detail

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
        return self._resolve_creature_etb(permanent, spell, card_info, counters)

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
        add_until_eot_pt_modifier(
            target,
            power_delta=power,
            toughness_delta=toughness,
            source_obj_id=spell.obj_id,
        )
        return f"{card_info.name} pumped {target.name} (+{power}/+{toughness})"

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
            detail = connive(self.state.zones, controller_idx, oracle, self._draw_cards, self.state)
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

    def _deal_damage_to_player(self, player_idx: int, amount: int) -> None:
        """Deal damage to a player and mark Raid-related flags."""
        if amount <= 0:
            return
        self.state.players[player_idx].life -= amount
        self.state.mark_player_was_dealt_damage(player_idx)
