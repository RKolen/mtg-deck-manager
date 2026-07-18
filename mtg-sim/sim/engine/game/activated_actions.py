"""Activated keyword actions for InteractiveGame (Phase E8)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from deck_registry import CardInfo
from engine.abilities import activated
from engine.abilities.activated.core import _ActivationCall
from engine.abilities.activated.fetchland import (
    PendingFetchland,
    complete_fetchland_at_index,
    fetchland_life_cost,
    is_fetchland_spec,
    list_fetch_search_options,
)
from engine.abilities.keywords.other.forecast import can_forecast, forecast_draws_card
from engine.abilities.keywords.other.encore import sacrifice_encore_tokens
from engine.abilities.activated import ActivationSpeed
from engine.abilities.activated._cost_keyword import INSTANT_SPEED_PHASES
from engine.abilities.keywords.other.blitz import sacrifice_blitz_creatures
from engine.abilities.keywords.other.decayed import sacrifice_decayed_creatures
from engine.abilities.keywords.other.dash import return_dash_creatures_to_hand
from engine.core.game_object import CardObject, Permanent
from engine.core.zones import Zone
from engine.game._hand_card import load_hand_card_for_action, run_with_hand_card
from engine.game.runtime import GameRuntimeMixin

if TYPE_CHECKING:
    from engine.game.interactive import _GameSetup


class ActivatedActionsMixin(GameRuntimeMixin):
    """Cycling, channel, crew, unearth, level up, and permanent activations."""

    if TYPE_CHECKING:
        _setup: _GameSetup

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

    def _resolve_fetchland_activation(
        self,
        perm: Permanent,
        spec: activated.ActivatedAbilitySpec,
        speed: activated.ActivationSpeed,
    ) -> activated.ActivationResult:
        """Pay costs, sacrifice, and resolve a fetchland search immediately."""
        if not activated.can_activate(perm, spec, self.state, 0, speed):
            return activated.ActivationResult(ok=False, detail="Cannot activate now")
        mana_needed = activated.activation_mana_value(spec.cost_text)
        if mana_needed and not self._pay_mana_for_action(0, cost_text=spec.cost_text):
            return activated.ActivationResult(ok=False, detail=f"Need {mana_needed} mana")
        life_cost = fetchland_life_cost(spec.cost_text)
        if life_cost > 0:
            player = self.state.players[0]
            if player.life <= life_cost:
                return activated.ActivationResult(ok=False, detail="Not enough life")
            player.life -= life_cost
        did_tap = False
        if activated.requires_tap(spec.cost_text):
            perm.tapped = True
            did_tap = True
        self._setup.pending_fetchland = PendingFetchland(
            source_uid=str(perm.obj_id),
            effect_text=spec.effect_text,
            life_paid=life_cost,
            did_tap=did_tap,
        )
        option_count = len(list_fetch_search_options(
            self._zones(0).library,
            spec.effect_text,
        ))
        if option_count == 0:
            self._cancel_pending_fetchland()
            return activated.ActivationResult(
                ok=False,
                detail="No matching lands in your library",
            )
        return activated.ActivationResult(
            ok=True,
            detail=f"Search your library ({option_count} lands)",
            used_stack=False,
        )

    def _cancel_pending_fetchland(self) -> None:
        """Refund a pending fetchland activation and clear the search state."""
        pending = self._setup.pending_fetchland
        if pending is None:
            return
        perm = self._find_permanent(pending.source_uid)
        if perm is not None:
            if pending.did_tap:
                perm.tapped = False
            if pending.life_paid > 0:
                self.state.players[0].life += pending.life_paid
        self._setup.pending_fetchland = None

    def action_fetch_land(
        self,
        library_idx: int,
        *,
        pay_shockland_life: bool = False,
    ) -> dict:
        """Complete a pending fetchland search with the chosen library card."""
        pending = self._setup.pending_fetchland
        if pending is None:
            return self._client_error("No fetchland search in progress")
        if library_idx < 0:
            return self._client_error("Choose a land from your library")
        perm = self._find_permanent(pending.source_uid)
        if perm is None:
            self._setup.pending_fetchland = None
            return self._client_error("Fetchland source not found")
        detail = complete_fetchland_at_index(
            self.state,
            perm,
            pending.effect_text,
            library_idx,
            pay_shockland_life=pay_shockland_life,
        )
        if detail is None:
            return self._client_error("Invalid land choice")
        self._setup.pending_fetchland = None
        self.state.check_sbas()
        self._log("player", "fetch", detail)
        return self.to_client()

    def action_cancel_fetch(self) -> dict:
        """Cancel a pending fetchland search and refund its costs."""
        if self._setup.pending_fetchland is None:
            return self._client_error("No fetchland search in progress")
        self._cancel_pending_fetchland()
        self._log("player", "fetch", "Cancelled fetchland search")
        return self.to_client()

    def _fetch_search_to_client(self) -> dict | None:
        """Serialise pending fetchland search options for the play UI."""
        pending = self._setup.pending_fetchland
        if pending is None:
            return None
        options = list_fetch_search_options(self._zones(0).library, pending.effect_text)
        return {
            "sourceUid": pending.source_uid,
            "fetchableNames": [option.name for option in options],
        }

    def _resolve_stack_activation(
        self,
        perm: Permanent,
        spec: activated.ActivatedAbilitySpec,
        ability_idx: int,
        speed: activated.ActivationSpeed,
    ) -> activated.ActivationResult:
        """Resolve a non-mana, non-equip activation onto the stack."""
        if not activated.can_activate(perm, spec, self.state, 0, speed):
            return activated.ActivationResult(ok=False, detail="Cannot activate now")
        loyalty = activated.loyalty_cost_change(spec.cost_text)
        mana_needed = activated.activation_mana_value(spec.cost_text)
        if mana_needed and not self._pay_mana_for_action(0, cost_text=spec.cost_text):
            return activated.ActivationResult(ok=False, detail=f"Need {mana_needed} mana")
        if loyalty is not None and not activated.can_pay_loyalty(perm, loyalty):
            return activated.ActivationResult(ok=False, detail="Not enough loyalty")
        return activated.activate_on_stack(
            self.state,
            perm,
            spec,
            _ActivationCall(ability_idx=ability_idx, mana_paid=True),
        )

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
        elif is_fetchland_spec(spec):
            result = self._resolve_fetchland_activation(perm, spec, speed)
        else:
            result = self._resolve_stack_activation(perm, spec, ability_idx, speed)
        if not result.ok:
            return self._client_error(result.detail)
        self._log("player", "activate", result.detail)
        return self.to_client()

    def _finish_player_action(self, action: str, detail: str) -> dict:
        """Log a player action and return the updated client state."""
        self._log("player", action, detail)
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
        if not self._pay_mana_for_action(
            0,
            cost=activated.cycling_cost(card_info),
            mana_needed=activated.cycling_mana_needed(card_info),
        ):
            cycle_needed = activated.cycling_mana_needed(card_info)
            return {**self.to_client(), "error": f"Need {cycle_needed} mana to cycle"}
        activated.cycle_from_hand(self.state.zones, 0, hand_idx, self.state)
        drawn = self._draw_cards(0, 1)
        return self._finish_player_action("cycle", f"Cycled {card_info.name}, drew {len(drawn)}")

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
        if not self._pay_mana_for_action(
            0,
            cost=activated.channel_cost(card_info),
            mana_needed=activated.channel_mana_needed(card_info),
        ):
            channel_needed = activated.channel_mana_needed(card_info)
            return {**self.to_client(), "error": f"Need {channel_needed} mana to channel"}
        effect = activated.channel_effect(card_info)
        activated.discard_for_channel(self.state.zones, 0, hand_idx, self.state)
        detail = f"Channeled {card_info.name}"
        draw_count = activated.channel_draw(effect)
        if draw_count:
            drawn = self._draw_cards(0, draw_count)
            detail = f"{detail}, drew {len(drawn)}"
        damage = activated.channel_damage(effect)
        if damage and target_player is not None:
            self.state.players[target_player].life -= damage
            detail = f"{detail}, dealt {damage}"
        return self._finish_player_action("channel", detail)

    def action_unearth(self, graveyard_idx: int) -> dict:
        """Activate unearth from the graveyard."""
        card, card_info, err = self._load_graveyard_card(0, graveyard_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        if not activated.can_unearth(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot unearth now"}
        if not self._pay_mana_for_action(
            0,
            cost=activated.unearth_cost(card_info),
            mana_needed=activated.unearth_mana_needed(card_info),
        ):
            unearth_needed = activated.unearth_mana_needed(card_info)
            return {**self.to_client(), "error": f"Need {unearth_needed} mana to unearth"}
        activated.unearth_from_graveyard(self.state.zones, 0, graveyard_idx)
        return self._finish_player_action("unearth", f"Unearthed {card_info.name}")

    def action_scavenge(self, graveyard_idx: int, target_uid: str | None) -> dict:
        """Activate scavenge from the graveyard onto a creature."""
        card, card_info, err = self._load_graveyard_card(0, graveyard_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
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
        if not self._pay_mana_for_action(
            0,
            cost=activated.scavenge_cost(card_info),
            mana_needed=activated.scavenge_mana_needed(card_info),
        ):
            scavenge_needed = activated.scavenge_mana_needed(card_info)
            return {**self.to_client(), "error": f"Need {scavenge_needed} mana to scavenge"}
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
