"""Keyword activated actions split from ActivatedActionsMixin."""

from __future__ import annotations

from deck_registry import CardInfo
from engine.abilities import activated
from engine.abilities.activated.bloodrush import (
    apply_bloodrush,
    bloodrush_mana_needed,
    can_bloodrush,
    bloodrush_cost,
)
from engine.abilities.keywords.other.craft import (
    apply_craft,
    craft_artifact_error,
    craft_mana_needed,
    has_craft,
    _CRAFT_ACTIVATION_RE,
)
from engine.abilities.keywords.other.boast import (
    apply_boast,
    boast_mana_needed,
    can_boast,
    _BOAST_RE,
)
from engine.abilities.keywords.other.exhaust import (
    can_use_exhaust_ability,
    has_exhaust,
    mark_exhaust_used,
)
from engine.abilities.keywords.other.encore import (
    apply_encore_from_graveyard,
    can_encore,
    encore_mana_needed,
    _ENCORE_RE,
)
from engine.abilities.keywords.other.eternalize import (
    apply_eternalize_from_graveyard,
    can_eternalize,
    eternalize_mana_needed,
    _ETERNALIZE_RE,
)
from engine.abilities.keywords.casting.embalm import (
    can_embalm,
    create_embalm_token_in_exile,
    embalm_mana_needed,
    has_embalm,
    embalm_cost,
)
from engine.abilities.keywords.other.disguise import (
    apply_turn_up_disguise,
    can_turn_up_disguise,
    disguise_turn_up_mana_needed,
    disguise_turn_up_cost,
)
from engine.abilities.keywords.other.morph import (
    apply_turn_up_morph,
    can_turn_up_morph,
    morph_turn_up_mana_needed,
    morph_turn_up_cost,
)
from engine.abilities.keywords.other.outlast import (
    apply_outlast,
    can_outlast,
    outlast_cost,
    outlast_mana_needed,
)
from engine.abilities.keywords.other.transmute import (
    apply_transmute,
    can_transmute,
    transmute_cost,
    transmute_mana_needed,
)
from engine.abilities.keywords.other.transfigure import (
    apply_transfigure,
    can_transfigure,
    transfigure_cost,
    transfigure_mana_needed,
)
from engine.abilities.keywords.other.aura_swap import (
    apply_aura_swap,
    aura_swap_cost,
    aura_swap_mana_needed,
    can_aura_swap,
)
from engine.abilities.keywords.other.reconfigure import apply_reconfigure, can_reconfigure
from engine.abilities.keywords.other.station import (
    apply_station,
    can_station,
    station_cost,
    station_power_error,
)
from engine.abilities.keywords.other.commander_ninjutsu import (
    apply_commander_ninjutsu,
    can_commander_ninjutsu,
    commander_ninjutsu_mana_needed,
    _COMMANDER_NINJUTSU_RE,
)
from engine.abilities.keywords.other.hidden_agenda import (
    register_double_agenda,
    reveal_double_agenda,
)
from engine.abilities.keywords.other.ninjutsu import (
    apply_ninjutsu,
    can_ninjutsu,
    ninjutsu_mana_needed,
    _NINJUTSU_RE,
)
from engine.abilities.activated._cost_keyword import parse_alt_cost
from engine.core.game_object import Permanent
from engine.game._hand_card import load_hand_card_for_action
from engine.game.activated_actions import ActivatedActionsMixin


class ActivatedActionsKeywordsMixin(ActivatedActionsMixin):
    """Bloodrush, ninjutsu, boast, and other keyword activations."""

    def action_bloodrush(self, hand_idx: int, target_creature_uid: str | None) -> dict:
        """Bloodrush from hand: pay, discard, pump a creature."""
        card, card_info, err = load_hand_card_for_action(self, hand_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        if not can_bloodrush(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot bloodrush now"}
        if not self._pay_mana_for_action(
            0,
            cost=bloodrush_cost(card_info),
            mana_needed=bloodrush_mana_needed(card_info),
        ):
            return {
                **self.to_client(),
                "error": f"Need {bloodrush_mana_needed(card_info)} mana to bloodrush",
            }
        detail = apply_bloodrush(
            self.state.zones,
            0,
            hand_idx,
            target_creature_uid,
            self.state,
        )
        if detail is None:
            return {**self.to_client(), "error": "Bloodrush failed"}
        return self._finish_player_action("bloodrush", detail)

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
        if not self._pay_mana_for_action(
            0,
            cost=parse_alt_cost(card_info, _NINJUTSU_RE),
            mana_needed=ninjutsu_mana_needed(card_info),
        ):
            return {
                **self.to_client(),
                "error": f"Need {ninjutsu_mana_needed(card_info)} mana for ninjutsu",
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

    def action_commander_ninjutsu(self, attacker_uid: str | None) -> dict:
        """Commander ninjutsu from the command zone during combat."""
        commander = self.state.players[0].commander
        if commander is None or commander.card_info is None:
            return {**self.to_client(), "error": "No commander in command zone"}
        card_info = commander.card_info
        if not can_commander_ninjutsu(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot commander ninjutsu now"}
        if not self._pay_mana_for_action(
            0,
            cost=parse_alt_cost(card_info, _COMMANDER_NINJUTSU_RE),
            mana_needed=commander_ninjutsu_mana_needed(card_info),
        ):
            return {
                **self.to_client(),
                "error": (
                    f"Need {commander_ninjutsu_mana_needed(card_info)} mana"
                    " for commander ninjutsu"
                ),
            }
        detail = apply_commander_ninjutsu(
            self.state,
            self.state.zones,
            0,
            attacker_uid,
        )
        if detail is None:
            return {**self.to_client(), "error": "Commander ninjutsu failed"}
        self._log("player", "commander_ninjutsu", detail)
        return self.to_client()

    def action_register_double_agenda(
        self,
        first_name: str,
        second_name: str,
    ) -> dict:
        """Secretly choose two card names for double agenda."""
        register_double_agenda(self.state, 0, first_name, second_name)
        self._log("player", "double_agenda", "double agenda registered")
        return self.to_client()

    def action_reveal_double_agenda(self) -> dict:
        """Reveal a double agenda choice."""
        detail = reveal_double_agenda(self.state, 0)
        if detail is None:
            return {**self.to_client(), "error": "Cannot reveal double agenda"}
        self._log("player", "double_agenda", detail)
        return self.to_client()

    def action_boast(self, permanent_uid: str) -> dict:
        """Activate boast on an attacking creature."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        is_attacking = permanent_uid in self.pending_attackers
        if not can_boast(perm, self.phase, is_attacking=is_attacking):
            return self._client_error("Cannot boast now")
        if has_exhaust(perm) and not can_use_exhaust_ability(perm):
            return self._client_error("Exhaust ability already used")
        boast_match = _BOAST_RE.search(perm.oracle_text or '')
        if not self._pay_mana_for_action(
            0,
            cost_text=boast_match.group(1) if boast_match else None,
            mana_needed=boast_mana_needed(perm),
        ):
            return self._client_error(f"Need {boast_mana_needed(perm)} mana to boast")
        detail = apply_boast(perm, 0, self._draw_cards)
        if detail is None:
            return self._client_error("Boast failed")
        if has_exhaust(perm):
            mark_exhaust_used(perm)
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
        craft_match = _CRAFT_ACTIVATION_RE.search(perm.oracle_text or '')
        if not self._pay_mana_for_action(
            0,
            cost_text=craft_match.group(1) if craft_match else None,
            mana_needed=craft_mana_needed(perm),
        ):
            return self._client_error(f"Need {craft_mana_needed(perm)} mana to craft")
        detail = apply_craft(self.state, perm, artifact_ids)
        if detail is None:
            return self._client_error("Craft failed")
        return self._finish_player_action("craft", detail)

    def action_encore(self, graveyard_idx: int) -> dict:
        """Activate encore from the graveyard."""
        card, card_info, err = self._load_graveyard_card(0, graveyard_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        if not can_encore(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot encore now"}
        if not self._pay_mana_for_action(
            0,
            cost=parse_alt_cost(card_info, _ENCORE_RE),
            mana_needed=encore_mana_needed(card_info),
        ):
            encore_needed = encore_mana_needed(card_info)
            return {**self.to_client(), "error": f"Need {encore_needed} mana to encore"}
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
        card, card_info, err = self._load_graveyard_card(0, graveyard_idx)
        if err is not None:
            return err
        assert card is not None and card_info is not None
        if not can_eternalize(card_info, self.phase, self.state.stack.is_empty):
            return {**self.to_client(), "error": "Cannot eternalize now"}
        if not self._pay_mana_for_action(
            0,
            cost=parse_alt_cost(card_info, _ETERNALIZE_RE),
            mana_needed=eternalize_mana_needed(card_info),
        ):
            eternalize_needed = eternalize_mana_needed(card_info)
            return {
                **self.to_client(),
                "error": f"Need {eternalize_needed} mana to eternalize",
            }
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
        if has_exhaust(perm) and not can_use_exhaust_ability(perm):
            return self._client_error("Exhaust ability already used")
        if not self._pay_mana_for_action(
            0,
            cost=outlast_cost(perm),
            mana_needed=outlast_mana_needed(perm),
        ):
            return self._client_error(f"Need {outlast_mana_needed(perm)} mana to outlast")
        detail = apply_outlast(perm)
        if detail is None:
            return self._client_error("Outlast failed")
        if has_exhaust(perm):
            mark_exhaust_used(perm)
        self._log("player", "outlast", detail)
        return self.to_client()

    def action_transmute(self, permanent_uid: str) -> dict:
        """Activate transmute on a permanent."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        if not can_transmute(perm, self.state, 0, self.phase):
            return self._client_error("Cannot transmute now")
        if not self._pay_mana_for_action(
            0,
            cost=transmute_cost(perm),
            mana_needed=transmute_mana_needed(perm),
        ):
            return self._client_error(f"Need {transmute_mana_needed(perm)} mana to transmute")
        detail = apply_transmute(self.state, perm)
        if detail is None:
            return self._client_error("Transmute failed")
        self._log("player", "transmute", detail)
        return self.to_client()

    def action_transfigure(self, permanent_uid: str) -> dict:
        """Activate transfigure on a creature."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        if not can_transfigure(perm, self.state, 0, self.phase):
            return self._client_error("Cannot transfigure now")
        if not self._pay_mana_for_action(
            0,
            cost=transfigure_cost(perm),
            mana_needed=transfigure_mana_needed(perm),
        ):
            return self._client_error(f"Need {transfigure_mana_needed(perm)} mana to transfigure")
        detail = apply_transfigure(self.state, perm)
        if detail is None:
            return self._client_error("Transfigure failed")
        self._log("player", "transfigure", detail)
        return self.to_client()

    def action_aura_swap(self, permanent_uid: str, hand_idx: int) -> dict:
        """Activate aura swap on an Aura."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        if not can_aura_swap(perm, self.state, 0, self.phase):
            return self._client_error("Cannot aura swap now")
        if not self._pay_mana_for_action(
            0,
            cost=aura_swap_cost(perm),
            mana_needed=aura_swap_mana_needed(perm),
        ):
            return self._client_error(f"Need {aura_swap_mana_needed(perm)} mana to aura swap")
        detail = apply_aura_swap(self.state, perm, hand_idx)
        if detail is None:
            return self._client_error("Aura swap failed")
        self._log("player", "aura_swap", detail)
        return self.to_client()

    def action_reconfigure(self, permanent_uid: str) -> dict:
        """Toggle reconfigure on a permanent."""
        perm = self._find_permanent(permanent_uid)
        if perm is None:
            return self._client_error("Permanent not found")
        if not can_reconfigure(perm, self.state, 0, self.phase):
            return self._client_error("Cannot reconfigure now")
        detail = apply_reconfigure(perm)
        if detail is None:
            return self._client_error("Reconfigure failed")
        self._log("player", "reconfigure", detail)
        return self.to_client()

    def _apply_turn_up(
        self, perm: Permanent, card_info: CardInfo
    ) -> tuple[str, str] | str:
        """Apply morph/disguise turn-up; return (detail, action) or error string."""
        if can_turn_up_morph(perm, self.state, 0, self.phase):
            morph_cost = morph_turn_up_cost(card_info)
            if not self._pay_mana_for_action(
                0,
                cost=morph_cost,
                mana_needed=morph_turn_up_mana_needed(card_info),
            ):
                return f"Need {morph_turn_up_mana_needed(card_info)} mana to turn face up"
            detail = apply_turn_up_morph(perm)
            return (detail, "turn_up_morph") if detail is not None else "Turn face up failed"
        if can_turn_up_disguise(perm, self.state, 0, self.phase):
            disguise_cost = disguise_turn_up_cost(card_info)
            if not self._pay_mana_for_action(
                0,
                cost=disguise_cost,
                mana_needed=disguise_turn_up_mana_needed(card_info),
            ):
                return f"Need {disguise_turn_up_mana_needed(card_info)} mana to turn face up"
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
        if not self._pay_mana_for_action(
            0,
            cost=embalm_cost(card_info),
            mana_needed=mana_needed,
        ):
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

    def action_station(
        self,
        spacecraft_uid: str,
        crewer_uids: list[str],
    ) -> dict:
        """Station a spacecraft by tapping creatures with enough total power."""
        spacecraft = self._find_permanent(spacecraft_uid)
        if spacecraft is None:
            return {**self.to_client(), "error": "Spacecraft not found"}
        if not can_station(spacecraft, self.state, 0, self.phase):
            return {**self.to_client(), "error": "Cannot station now"}
        required = station_cost(spacecraft) or 1
        err = station_power_error(self.state, 0, crewer_uids, required)
        if err:
            return {**self.to_client(), "error": err}
        apply_station(self.state, spacecraft, crewer_uids)
        self._log("player", "station", f"Stationed {spacecraft.name} ({required})")
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
        if not self._pay_mana_for_action(
            0,
            cost=activated.level_up_cost(perm),
            mana_needed=activated.level_up_mana_needed(perm),
        ):
            level_needed = activated.level_up_mana_needed(perm)
            return {**self.to_client(), "error": f"Need {level_needed} mana to level up"}
        level = activated.apply_level_up(perm)
        self._log("player", "level_up", f"{perm.name} is level {level}")
        return self.to_client()
