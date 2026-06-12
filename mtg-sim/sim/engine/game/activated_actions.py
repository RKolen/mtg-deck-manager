"""Activated keyword actions for InteractiveGame (Phase E8)."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities import activated
from engine.abilities.activated.core import _ActivationCall
from engine.abilities.activated.bloodrush import (
    apply_bloodrush,
    bloodrush_mana_needed,
    can_bloodrush,
)
from engine.abilities.keywords.other.craft import (
    apply_craft,
    craft_artifact_error,
    craft_mana_needed,
    has_craft,
)
from engine.abilities.keywords.other.boast import (
    apply_boast,
    boast_mana_needed,
    can_boast,
)
from engine.abilities.keywords.other.forecast import can_forecast, forecast_draws_card
from engine.abilities.keywords.other.encore import (
    apply_encore_from_graveyard,
    can_encore,
    encore_mana_needed,
    sacrifice_encore_tokens,
)
from engine.abilities.keywords.other.eternalize import (
    apply_eternalize_from_graveyard,
    can_eternalize,
    eternalize_mana_needed,
)
from engine.abilities.keywords.casting.embalm import (
    can_embalm,
    create_embalm_token_in_exile,
    embalm_mana_needed,
    has_embalm,
)
from engine.abilities.keywords.other.disguise import (
    apply_turn_up_disguise,
    can_turn_up_disguise,
    disguise_turn_up_mana_needed,
)
from engine.abilities.keywords.other.morph import (
    apply_turn_up_morph,
    can_turn_up_morph,
    morph_turn_up_mana_needed,
)
from engine.abilities.keywords.other.outlast import (
    apply_outlast,
    can_outlast,
    outlast_mana_needed,
)
from engine.abilities.keywords.other.ninjutsu import (
    apply_ninjutsu,
    can_ninjutsu,
    ninjutsu_mana_needed,
)
from engine.abilities.activated import ActivationSpeed
from engine.abilities.activated._cost_keyword import INSTANT_SPEED_PHASES
from engine.abilities.keywords.other.blitz import sacrifice_blitz_creatures
from engine.abilities.keywords.other.decayed import sacrifice_decayed_creatures
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
                _ActivationCall(ability_idx=ability_idx, mana_paid=True),
            )
        if not result.ok:
            return self._client_error(result.detail)
        self._log("player", "activate", result.detail)
        return self.to_client()

    def action_cycle(self, hand_idx: int) -> dict:
        """Activate cycling from hand: pay, discard, draw."""
        return run_with_hand_card(self, hand_idx, lambda c, i: self._resolve_cycle(c, i, hand_idx))

    def action_forecast(self, hand_idx: int) -> dict:
        """Forecast from hand during the draw step (simplified upkeep window)."""
        _card, card_info, err = load_hand_card_for_action(self, hand_idx)
        if err is not None:
            return err
        assert card_info is not None
        if not can_forecast(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot forecast now"}
        drawn = 0
        if forecast_draws_card(card_info):
            drawn = len(self._draw_cards(0, 1))
        self._log("player", "forecast", f"Forecast {card_info.name} (drew {drawn})")
        return self.to_client()

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

    def action_bloodrush(self, hand_idx: int, target_creature_uid: str | None) -> dict:
        """Bloodrush from hand: pay, discard, pump a creature."""
        card, card_info, err = load_hand_card_for_action(self, hand_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        if not can_bloodrush(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot bloodrush now"}
        mana_needed = bloodrush_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": f"Need {mana_needed} mana to bloodrush",
            }
        detail = apply_bloodrush(
            self.state.zones,
            0,
            hand_idx,
            target_creature_uid,
        )
        if detail is None:
            return {**self.to_client(), "error": "Bloodrush failed"}
        self._log("player", "bloodrush", detail)
        return self.to_client()

    def action_ninjutsu(
        self,
        hand_idx: int,
        attacker_uid: str | None,
    ) -> dict:
        """Ninjutsu from hand during combat."""
        card, card_info, err = load_hand_card_for_action(self, hand_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        if not can_ninjutsu(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot ninjutsu now"}
        mana_needed = ninjutsu_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": f"Need {mana_needed} mana for ninjutsu",
            }
        detail = apply_ninjutsu(
            self.state,
            self.state.zones,
            0,
            hand_idx,
            attacker_uid,
        )
        if detail is None:
            return {**self.to_client(), "error": "Ninjutsu failed"}
        self._log("player", "ninjutsu", detail)
        return self.to_client()

    def action_boast(self, permanent_uid: str) -> dict:
        """Activate boast on an attacking creature."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        is_attacking = permanent_uid in self.pending_attackers
        if not can_boast(perm, self.phase, is_attacking=is_attacking):
            return self._client_error("Cannot boast now")
        mana_needed = boast_mana_needed(perm)
        if mana_needed and not self._tap_lands_for_mana(0, mana_needed):
            return self._client_error(f"Need {mana_needed} mana to boast")
        detail = apply_boast(perm, 0, self._draw_cards)
        if detail is None:
            return self._client_error("Boast failed")
        self._log("player", "boast", detail)
        return self.to_client()

    def action_craft(
        self,
        permanent_uid: str,
        artifact_uids: list[str],
    ) -> dict:
        """Activate craft by exiling artifacts you control."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        if not has_craft(perm):
            return self._client_error("Permanent does not have craft")
        artifact_ids = [int(uid) for uid in artifact_uids]
        err = craft_artifact_error(self.state, perm, 0, artifact_ids)
        if err:
            return self._client_error(err)
        mana_needed = craft_mana_needed(perm)
        if mana_needed and not self._tap_lands_for_mana(0, mana_needed):
            return self._client_error(f"Need {mana_needed} mana to craft")
        detail = apply_craft(self.state, perm, artifact_ids)
        if detail is None:
            return self._client_error("Craft failed")
        self._log("player", "craft", detail)
        return self.to_client()

    def action_encore(self, graveyard_idx: int) -> dict:
        """Activate encore from the graveyard."""
        card, err = self._graveyard_card_checked(0, graveyard_idx)
        if err is not None:
            return err
        assert card is not None
        card_info = require_card_info(card)
        if not can_encore(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot encore now"}
        mana_needed = encore_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {**self.to_client(), "error": f"Need {mana_needed} mana to encore"}
        detail = apply_encore_from_graveyard(
            self.state,
            self.state.zones,
            0,
            graveyard_idx,
        )
        if detail is None:
            return {**self.to_client(), "error": "Encore failed"}
        self._log("player", "encore", detail)
        return self.to_client()

    def action_eternalize(self, graveyard_idx: int) -> dict:
        """Activate eternalize from the graveyard."""
        card, err = self._graveyard_card_checked(0, graveyard_idx)
        if err is not None:
            return err
        assert card is not None
        card_info = require_card_info(card)
        if not can_eternalize(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot eternalize now"}
        mana_needed = eternalize_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {**self.to_client(), "error": f"Need {mana_needed} mana to eternalize"}
        detail = apply_eternalize_from_graveyard(
            self.state.zones,
            0,
            graveyard_idx,
        )
        if detail is None:
            return {**self.to_client(), "error": "Eternalize failed"}
        self._log("player", "eternalize", detail)
        return self.to_client()

    def action_outlast(self, permanent_uid: str) -> dict:
        """Activate outlast on a creature."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        if not can_outlast(perm, self.state, 0, self.phase):
            return self._client_error("Cannot outlast now")
        mana_needed = outlast_mana_needed(perm)
        if mana_needed and not self._tap_lands_for_mana(0, mana_needed):
            return self._client_error(f"Need {mana_needed} mana to outlast")
        detail = apply_outlast(perm)
        if detail is None:
            return self._client_error("Outlast failed")
        self._log("player", "outlast", detail)
        return self.to_client()

    def _apply_turn_up(
        self, perm: Permanent, card_info: CardInfo
    ) -> tuple[str, str] | str:
        """Apply morph/disguise turn-up; return (detail, action) or error string."""
        if can_turn_up_morph(perm, self.state, 0, self.phase):
            mana_needed = morph_turn_up_mana_needed(card_info)
            if mana_needed and not self._tap_lands_for_mana(0, mana_needed):
                return f"Need {mana_needed} mana to turn face up"
            detail = apply_turn_up_morph(perm)
            return (detail, "turn_up_morph") if detail is not None else "Turn face up failed"
        if can_turn_up_disguise(perm, self.state, 0, self.phase):
            mana_needed = disguise_turn_up_mana_needed(card_info)
            if mana_needed and not self._tap_lands_for_mana(0, mana_needed):
                return f"Need {mana_needed} mana to turn face up"
            detail = apply_turn_up_disguise(perm)
            return (detail, "turn_up_disguise") if detail is not None else "Turn face up failed"
        return "Cannot turn face up now"

    def action_turn_up_morph(self, permanent_uid: str) -> dict:
        """Turn a face-down morph or disguise creature face up."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        card_info = perm.card_info
        if card_info is None:
            return self._client_error("Not a creature card")
        result = self._apply_turn_up(perm, card_info)
        if isinstance(result, str):
            return self._client_error(result)
        detail, action = result
        self._log("player", action, detail)
        return self.to_client()

    def action_embalm(self, hand_idx: int) -> dict:
        """Activate embalm from hand: pay cost, exile the card, create a token in exile."""
        card, card_info, err = load_hand_card_for_action(self, hand_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        if not can_embalm(card_info, self.phase, self.state.stack.is_empty):
            return self._client_error("Cannot embalm now")
        if not has_embalm(card_info):
            return self._client_error(f"{card_info.name} does not have embalm")
        mana_needed, life_cost = embalm_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return self._client_error(f"Need {mana_needed} mana to embalm")
        if life_cost:
            self.state.players[0].life -= life_cost
        hand = self.state.zones.player_zones[0].hand
        if hand_idx < 0 or hand_idx >= len(hand) or hand[hand_idx] is not card:
            return self._client_error("Invalid hand index")
        hand.pop(hand_idx)
        self.state.zones.player_zones[0].exile.append(card)
        detail = create_embalm_token_in_exile(
            self.state.zones,
            0,
            card_info,
            source_obj_id=card.obj_id,
        )
        self._log("player", "embalm", detail)
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

    def action_scavenge(self, graveyard_idx: int, target_uid: str | None) -> dict:
        """Activate scavenge from the graveyard onto a creature."""
        card, err = self._graveyard_card_checked(0, graveyard_idx)
        if err is not None:
            return err
        assert card is not None
        card_info = require_card_info(card)
        if not activated.can_scavenge(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot scavenge now"}
        if target_uid is None:
            return {**self.to_client(), "error": "Scavenge requires a target creature"}
        return self._apply_scavenge(graveyard_idx, card_info, target_uid)

    def _apply_scavenge(
        self, graveyard_idx: int, card_info: CardInfo, target_uid: str
    ) -> dict:
        """Execute the scavenge after validation: check target, pay mana, apply."""
        target = self._find_permanent(target_uid)
        if target is None:
            return {**self.to_client(), "error": "Scavenge target not found"}
        mana_needed = activated.scavenge_mana_needed(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {**self.to_client(), "error": f"Need {mana_needed} mana to scavenge"}
        err, detail = activated.scavenge_from_graveyard(
            self.state.zones,
            0,
            graveyard_idx,
            target,
        )
        if err:
            return {**self.to_client(), "error": err}
        self._log("player", "scavenge", detail or "scavenge")
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

    def _sacrifice_blitz_at_turn_end(self, player_idx: int) -> None:
        """Sacrifice blitzed creatures at end of turn."""
        for detail in sacrifice_blitz_creatures(self.state, player_idx):
            self._log('rules', 'blitz', detail)

    def _sacrifice_decayed_at_turn_end(self, player_idx: int) -> None:
        """Sacrifice decayed creatures at end of turn."""
        for detail in sacrifice_decayed_creatures(self.state, player_idx):
            self._log('rules', 'decayed', detail)

    def _sacrifice_encore_at_turn_end(self, player_idx: int) -> None:
        """Sacrifice encore tokens at end of turn."""
        for detail in sacrifice_encore_tokens(self.state, player_idx):
            self._log('rules', 'encore', detail)
