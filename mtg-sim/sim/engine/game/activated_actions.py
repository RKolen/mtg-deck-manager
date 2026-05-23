"""Activated keyword actions for InteractiveGame (Phase E8)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities import activated
from engine.abilities.activated import ActivationSpeed
from engine.abilities.activated._cost_keyword import INSTANT_SPEED_PHASES
from engine.abilities.keywords.other.afflict import apply_afflict_on_attack
from engine.abilities.keywords.other.annihilator import apply_annihilator_on_attack
from engine.abilities.keywords.other.blitz import sacrifice_blitz_creatures
from engine.abilities.keywords.other.dash import return_dash_creatures_to_hand
from engine.core.game_object import CardObject, Permanent
from engine.core.zones import Zone
from engine.game._hand_card import load_hand_card_for_action, run_with_hand_card
from engine.game.helpers import require_card_info
from engine.game.runtime import GameRuntimeMixin


class ActivatedActionsMixin(GameRuntimeMixin):
    """Cycling, channel, crew, unearth, level up, and permanent activations."""

    def _resolve_equip_activation(
        self,
        perm: Permanent,
        spec: activated.ActivatedAbilitySpec,
        host_uid: str | None,
    ) -> activated.ActivationResult:
        """Resolve an equip activation or return a failure result."""
        if host_uid is None:
            return activated.ActivationResult(ok=False, detail="Equip requires a host")
        host = self._find_permanent(host_uid)
        if host is None:
            return activated.ActivationResult(ok=False, detail="Host not found")
        return activated.activate_equip(self.state, perm, host, spec)

    def _resolve_mana_activation(
        self,
        perm: Permanent,
        spec: activated.ActivatedAbilitySpec,
    ) -> activated.ActivationResult:
        """Resolve a mana ability activation or return a failure result."""
        if not activated.can_activate(
            perm,
            spec,
            self.state,
            0,
            ActivationSpeed.INSTANT,
        ):
            return activated.ActivationResult(ok=False, detail="Cannot activate now")
        detail = activated.activate_mana_ability(self.state, perm, spec)
        return activated.ActivationResult(ok=bool(detail), detail=detail)

    def _activation_speed(self) -> activated.ActivationSpeed:
        """Return whether activations are at instant or sorcery speed."""
        if self.phase in INSTANT_SPEED_PHASES or not self.state.stack.is_empty:
            return activated.ActivationSpeed.INSTANT
        return activated.ActivationSpeed.SORCERY

    def action_activate(
        self,
        permanent_uid: str,
        ability_idx: int,
        host_uid: str | None = None,
    ) -> dict:
        """Activate mana, equip, or other abilities on a permanent."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        specs = activated.parse_activated_abilities(perm.oracle_text)
        if ability_idx < 0 or ability_idx >= len(specs):
            return self._client_error("Invalid ability index")
        spec = specs[ability_idx]
        speed = self._activation_speed()
        if spec.equip:
            result = self._resolve_equip_activation(perm, spec, host_uid)
        elif spec.mana_ability:
            result = self._resolve_mana_activation(perm, spec)
        else:
            if not activated.can_activate(perm, spec, self.state, 0, speed):
                return self._client_error("Cannot activate now")
            mana_needed = activated.activation_mana_value(spec.cost_text)
            if mana_needed and not self._tap_lands_for_mana(0, mana_needed):
                return self._client_error(f"Need {mana_needed} mana")
            result = activated.activate_on_stack(
                self.state,
                perm,
                spec,
                ability_idx,
                mana_paid=True,
            )
        if not result.ok:
            return self._client_error(result.detail)
        self._log("player", "activate", result.detail)
        return self.to_client()

    def action_cycle(self, hand_idx: int) -> dict:
        """Activate cycling from hand: pay, discard, draw."""
        return run_with_hand_card(self, hand_idx, lambda c, i: self._resolve_cycle(c, i, hand_idx))

    def _resolve_cycle(self, _card: CardObject, card_info: CardInfo, hand_idx: int) -> dict:
        if not activated.can_cycle(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot cycle now"}
        mana_needed = activated.cycling_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {**self.to_client(), "error": f"Need {mana_needed} mana to cycle"}
        activated.cycle_from_hand(self.state.zones, 0, hand_idx)
        drawn = self._draw_cards(0, 1)
        self._log("player", "cycle", f"Cycled {card_info.name}, drew {len(drawn)}")
        return self.to_client()

    def action_channel(
        self,
        hand_idx: int,
        target_player: int | None = None,
    ) -> dict:
        """Activate channel from hand: pay, discard, apply a simple effect."""
        card, card_info, err = load_hand_card_for_action(self, hand_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        if not activated.can_channel(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot channel now"}
        mana_needed = activated.channel_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {**self.to_client(), "error": f"Need {mana_needed} mana to channel"}
        effect = activated.channel_effect(card_info)
        activated.discard_for_channel(self.state.zones, 0, hand_idx)
        detail = f"Channeled {card_info.name}"
        draw_count = activated.channel_draw(effect)
        if draw_count:
            drawn = self._draw_cards(0, draw_count)
            detail = f"{detail}, drew {len(drawn)}"
        damage = activated.channel_damage(effect)
        if damage and target_player is not None:
            self.state.players[target_player].life -= damage
            detail = f"{detail}, dealt {damage}"
        self._log("player", "channel", detail)
        return self.to_client()

    def action_unearth(self, graveyard_idx: int) -> dict:
        """Activate unearth from the graveyard."""
        card, err = self._graveyard_card_checked(0, graveyard_idx)
        if err is not None:
            return err
        assert card is not None
        card_info = require_card_info(card)
        if not activated.can_unearth(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot unearth now"}
        mana_needed = activated.unearth_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {**self.to_client(), "error": f"Need {mana_needed} mana to unearth"}
        activated.unearth_from_graveyard(self.state.zones, 0, graveyard_idx)
        self._log("player", "unearth", f"Unearthed {card_info.name}")
        return self.to_client()

    def action_crew(
        self,
        vehicle_uid: str,
        crewer_uids: list[str],
    ) -> dict:
        """Crew a vehicle by tapping creatures with enough total power."""
        vehicle = self._find_permanent(vehicle_uid)
        if vehicle is None:
            return {**self.to_client(), "error": "Vehicle not found"}
        if not activated.can_crew(vehicle, self.state, 0, self.phase):
            return {**self.to_client(), "error": "Cannot crew now"}
        required = activated.crew_cost(vehicle)
        err = activated.crew_power_error(self.state, 0, crewer_uids, required)
        if err:
            return {**self.to_client(), "error": err}
        activated.apply_crew(self.state, vehicle, crewer_uids)
        self._log("player", "crew", f"Crewed {vehicle.name} ({required})")
        return self.to_client()

    def action_mount(
        self,
        mount_uid: str,
        mount_creature_uids: list[str],
    ) -> dict:
        """Mount a mount by tapping creatures with enough total power."""
        mount_perm = self._find_permanent(mount_uid)
        if mount_perm is None:
            return self._client_error("Mount not found")
        if not activated.can_mount(mount_perm, self.state, 0, self.phase):
            return self._client_error("Cannot mount now")
        required = activated.mount_cost(mount_perm)
        err = activated.mount_power_error(self.state, 0, mount_creature_uids, required)
        if err:
            return self._client_error(err)
        activated.apply_mount(self.state, mount_perm, mount_creature_uids)
        self._log("player", "mount", f"Mounted {mount_perm.name} ({required})")
        return self.to_client()

    def action_level_up(self, permanent_uid: str) -> dict:
        """Pay level up cost and put a level counter on a creature."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return {**self.to_client(), "error": "Permanent not found"}
        if not activated.can_level_up(perm, self.state, 0, self.phase):
            return {**self.to_client(), "error": "Cannot level up now"}
        mana_needed = activated.level_up_mana_needed(perm)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {**self.to_client(), "error": f"Need {mana_needed} mana to level up"}
        level = activated.apply_level_up(perm)
        self._log("player", "level_up", f"{perm.name} is level {level}")
        return self.to_client()

    def _exile_unearth_at_turn_end(self, player_idx: int) -> None:
        """Exile unearthed creatures at end of turn."""
        for perm in list(self._permanents(player_idx)):
            if activated.is_unearth_creature(perm):
                self.state.zones.leave_battlefield(perm, Zone.EXILE, "unearth")
                self._log("rules", "unearth_exile", f"{perm.name} exiled")

    def _return_dash_creatures_to_hand(self, player_idx: int) -> list[str]:
        """Return dashed creatures to hand at end of turn."""
        return return_dash_creatures_to_hand(self.state, player_idx)

    def _apply_attack_keywords(self, attacker_ids: list[str]) -> None:
        """Apply annihilator, afflict, and similar on-attack keywords."""
        for attacker_id in attacker_ids:
            perm = self._find_permanent(attacker_id)
            if perm is None:
                continue
            for apply_fn, tag in (
                (apply_annihilator_on_attack, 'annihilator'),
                (apply_afflict_on_attack, 'afflict'),
            ):
                detail = apply_fn(self.state, perm)
                if detail:
                    self._log('rules', tag, detail)

    def _sacrifice_blitz_at_turn_end(self, player_idx: int) -> None:
        """Sacrifice blitzed creatures at end of turn."""
        for detail in sacrifice_blitz_creatures(self.state, player_idx):
            self._log('rules', 'blitz', detail)
