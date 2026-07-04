"""Player combat actions and combat-phase helpers for InteractiveGame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords.other.afflict import apply_afflict_on_attack
from engine.abilities.keywords.other.banding import (
    attacking_band_size,
    banding_block_detail,
)
from engine.abilities.keywords.other.double_team import apply_double_team_on_attack
from engine.abilities.keywords.other.firebending import (
    apply_firebending_on_attack,
    clear_firebending_mana,
)
from engine.abilities.keywords.other.battle_cry import apply_battle_cry_on_attack
from engine.abilities.keywords.other.flanking import apply_flanking_on_block
from engine.abilities.keywords.other.boast import mark_attacked_this_turn
from engine.abilities.keywords.other.enlist import apply_enlist_on_attack
from engine.abilities.keywords.other.melee import apply_melee_on_mass_attack
from engine.abilities.keywords.other.mobilize import apply_mobilize_on_attack
from engine.abilities.keywords.other.myriad import apply_myriad_on_attack
from engine.abilities.keywords.other.annihilator import apply_annihilator_on_attack
from engine.abilities.keywords.other.exalted import apply_exalted_on_attack
from engine.abilities.keywords.other.frenzy import apply_frenzy_on_unblocked_attack
from engine.abilities.keywords.other.mentor import apply_mentor_on_attack
from engine.abilities.keywords.other.training import apply_training_on_attack
from engine.abilities.keywords.other.living_metal import (
    activate_living_metal_for_combat,
    deactivate_living_metal_after_combat,
)
from engine.abilities.keywords.other.provoke import assign_provoke_blocks
from engine.abilities.keywords.other.rampage import apply_rampage_on_block
from engine.core.turn_structure import Step
from engine.game.activated_actions_keywords import ActivatedActionsKeywordsMixin
from engine.abilities.keywords.other.boast import clear_boast_turn_counters
from engine.abilities.keywords.other.bushido import clear_bushido_combat_markers
from engine.abilities.keywords.other.cumulative_upkeep import resolve_cumulative_upkeep
from engine.abilities.keywords.other.daybound import resolve_daybound_upkeep
from engine.abilities.keywords.other.echo import resolve_echo_upkeep
from engine.abilities.keywords.other.epic import resolve_epic_upkeep
from engine.abilities.keywords.other.fading import resolve_fading_upkeep
from engine.abilities.keywords.other.outlast import clear_outlast_turn_marker
from engine.abilities.keywords.other.phasing import resolve_phasing_upkeep
from engine.abilities.keywords.other.recover import resolve_recover_upkeep
from engine.abilities.keywords.other.transmute import clear_transmute_turn_marker
from engine.abilities.keywords.other.vanishing import resolve_vanishing_upkeep
from engine.abilities.keywords.casting.paradigm import resolve_paradigm_upkeep
from engine.abilities.keywords.casting.rebound import resolve_rebound_upkeep
from engine.cards.oracle_parse import is_affordable, spell_category
from engine.core.game_object import CardObject
from engine.core.zones import Zone
from engine.game.cast_flow import _TargetRef
from engine.game.helpers import (
    card_names,
    is_land,
    payment_requirements,
    perm_names,
    require_card_info,
)
from engine.rules.combat import (
    can_attack,
    eligible_attackers,
    legal_blocker,
    resolve_combat_damage,
    tap_attackers,
)
from engine.rules.modifiers import clear_until_end_of_turn_modifiers

from deck_registry import CardInfo
from mcts import llm_pick


class CombatActionsMixin(ActivatedActionsKeywordsMixin):
    """Attack and block steps for the human player."""

    if TYPE_CHECKING:
        on_the_play: bool
        pilot_prompt: str
        player_pilot_prompt: str

        def action_play_land(self, _hand_idx: int) -> dict:
            """Play a land from the player's hand (defined in InteractiveGame)."""
            return {}

        def action_cast(self, _hand_idx: int) -> dict:
            """Cast a spell from the player's hand (defined in InteractiveGame)."""
            return {}

        def _tick_suspend_upkeep(self, player_idx: int) -> None:
            """Advance suspend counters during upkeep (defined in SpellStackMixin)."""

    def _start_player_turn_one(self) -> None:
        """Begin the first player-controlled turn after mulligans."""
        self._begin_turn(0)
        if self.on_the_play:
            self._log("system", "no_draw", "No draw on the play, turn 1")
        else:
            drawn = self._draw_cards(0, 1)
            self._log("player", "draw", f"Drew: {card_names(drawn) or '-'}")
        self.phase = "main1"

    def _begin_turn(self, player_idx: int) -> None:
        """Untap permanents and clear per-turn player state."""
        self.state.turn.begin_turn(player_idx)
        for perm in self._permanents(player_idx):
            clear_boast_turn_counters(perm)
            clear_bushido_combat_markers(perm)
            clear_outlast_turn_marker(perm)
            clear_transmute_turn_marker(perm)
            perm.counters.pop('valiant_this_turn', None)
            if perm.counters.pop('exerted', 0) or perm.counters.pop('detained', 0):
                continue
            perm.tapped = False
            perm.sick = False
            perm.damage_marked = 0
        player = self.state.players[player_idx]
        player.mana_pool.empty()
        player.land_played = False
        player.spells_cast_this_turn = 0
        player.combat_damage_dealt_this_turn = False
        player.was_dealt_damage_this_turn = False
        player.revolt_this_turn = False
        player.permanents_entered_this_turn = 0
        self.state.creature_died_this_turn = False
        self.state.meta.deaths.permanents_died = 0
        self._fire_step_triggers(Step.UPKEEP)
        for detail in resolve_echo_upkeep(
            self.state,
            player_idx,
            self._tap_lands_for_mana,
        ):
            self._log('rules', 'echo', detail)
        for detail in resolve_epic_upkeep(self.state, player_idx):
            self._log('rules', 'epic', detail)
        for detail in resolve_fading_upkeep(self.state, player_idx):
            self._log('rules', 'fading', detail)
        for detail in resolve_cumulative_upkeep(
            self.state,
            player_idx,
            self._tap_lands_for_mana,
        ):
            self._log('rules', 'cumulative_upkeep', detail)
        for detail in resolve_vanishing_upkeep(self.state, player_idx):
            self._log('rules', 'vanishing', detail)
        for detail in resolve_paradigm_upkeep(self.state, player_idx):
            self._log('rules', 'paradigm', detail)
        for detail in resolve_rebound_upkeep(self.state.zones, player_idx):
            self._log('rules', 'rebound', detail)
        for detail in resolve_recover_upkeep(self.state, player_idx):
            self._log('rules', 'recover', detail)
        for detail in resolve_phasing_upkeep(self.state, player_idx):
            self._log('rules', 'phasing', detail)
        for detail in resolve_daybound_upkeep(self.state, player_idx):
            self._log('rules', 'daybound', detail)
        self._tick_suspend_upkeep(player_idx)

    def run_opponent_main_phase(self) -> None:
        """Run a simple opponent draw, land, and spell sequence."""
        self._begin_turn(1)
        drawn = self._draw_cards(1, 1)
        if drawn:
            self._log(
                "opponent",
                "draw",
                f"Drew a card ({len(self._zones(1).hand)} in hand)",
            )
        land_idx = next(
            (
                idx for idx, card in enumerate(self._zones(1).hand)
                if isinstance(card, CardObject) and is_land(card)
            ),
            None,
        )
        if land_idx is not None:
            card = self._zones(1).hand[land_idx]
            if not isinstance(card, CardObject):
                return
            self.state.zones.enter_battlefield(card, 1, "play_land", Zone.HAND)
            self.state.players[1].land_played = True
            self._log("opponent", "land", require_card_info(card).name)
        self._opponent_cast_one_spell()
        self._check_game_over()

    def _llm_pick_spell(
        self,
        options: list[tuple[int, CardInfo]],
        player_idx: int,
        pilot_prompt: str,
        actor: str,
    ) -> tuple[int, CardInfo]:
        """Pick the best spell to cast from available options."""
        heuristic = sorted(
            options,
            key=lambda item: (not item[1].is_creature, item[1].cmc),
        )[0]
        if not pilot_prompt:
            return heuristic
        option_names = [
            f"{ci.name} ({ci.short_type()}, CMC {int(ci.cmc)})"
            for _, ci in options
        ]
        opp_idx = 1 - player_idx
        state = {
            "turn": self.state.turn.context.turn_number,
            "own_life": self.state.players[player_idx].life,
            "opp_life": self.state.players[opp_idx].life,
            "mana": self._available_mana(player_idx),
        }
        idx, reasoning = llm_pick(
            "Choose the ONE spell to cast that best serves your deck strategy.",
            option_names,
            state,
            system_prompt=pilot_prompt,
        )
        if not reasoning:
            return heuristic
        self._log(actor, "pick", reasoning)
        return options[idx]

    def _opponent_cast_one_spell(self) -> None:
        """Cast the best affordable opponent spell, guided by pilot prompt when set."""
        options = [
            (idx, require_card_info(card))
            for idx, card in enumerate(self._zones(1).hand)
            if (
                isinstance(card, CardObject)
                and not is_land(card)
                and is_affordable(require_card_info(card), self._available_mana(1))
            )
        ]
        if not options:
            return
        hand_idx, card_info = self._llm_pick_spell(
            options,
            player_idx=1,
            pilot_prompt=self.pilot_prompt,
            actor="pilot",
        )
        card = self._zones(1).hand[hand_idx]
        if not isinstance(card, CardObject):
            return
        mana_needed, _ = payment_requirements(card_info)
        if not self._tap_mana_for_spell(1, card_info, mana_needed):
            return
        target_player = 0 if spell_category(card_info) == "burn" else None
        targets = self._put_spell_on_stack(
            player_idx=1,
            card=card,
            target_ref=_TargetRef(None, target_player),
        )
        self._log("opponent", "cast", f"{card_info.name} on stack")
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        self._auto_pass_stack()

    def _player_castable_spell_options(self) -> list[tuple[int, CardInfo]]:
        """Return affordable non-land spells in the player's hand."""
        hand = self._zones(0).hand
        return [
            (i, require_card_info(card))
            for i, card in enumerate(hand)
            if isinstance(card, CardObject)
            and not is_land(card)
            and self._is_card_castable(card)
        ]

    def _player_play_land_if_needed(self) -> None:
        """Play the first available land when none has been played this turn."""
        if self.state.players[0].land_played:
            return
        hand = self._zones(0).hand
        for i, card in enumerate(hand):
            if isinstance(card, CardObject) and is_land(card):
                self.action_play_land(i)
                break

    def action_auto_main(self) -> dict:
        """Auto-play the player's main phase, using deck notes when configured."""
        assert self.phase in ("main1", "main2")
        self._player_play_land_if_needed()
        while self.phase != "game_over":
            options = self._player_castable_spell_options()
            if not options:
                break
            if self.player_pilot_prompt:
                hand_idx, _ = self._llm_pick_spell(
                    options,
                    player_idx=0,
                    pilot_prompt=self.player_pilot_prompt,
                    actor="player_pilot",
                )
            else:
                hand_idx = sorted(
                    options,
                    key=lambda item: (not item[1].is_creature, item[1].cmc),
                )[0][0]
            result = self.action_cast(hand_idx)
            if result.get("error"):
                break
        return self.to_client()

    def action_auto_attack(self) -> dict:
        """Auto-attack with all eligible player creatures and confirm combat."""
        assert self.phase == "attack"
        for perm in eligible_attackers(self._permanents(0)):
            self.action_toggle_attacker(str(perm.obj_id))
        return self.action_confirm_attack()

    def action_go_to_attack(self) -> dict:
        """Move from first main phase to declare attackers."""
        assert self.phase == "main1"
        self._fire_step_triggers(Step.BEGIN_COMBAT)
        for detail in activate_living_metal_for_combat(self.state, 0):
            self._log('rules', 'living_metal', detail)
        self.phase = "attack"
        self.pending_attackers = []
        return self.to_client()

    def action_toggle_attacker(self, uid: str) -> dict:
        """Toggle one eligible attacking creature."""
        assert self.phase == "attack"
        if uid in self.pending_attackers:
            self.pending_attackers.remove(uid)
            return self.to_client()
        perm = self._find_permanent(uid)
        if perm is not None and perm.controller_idx == 0 and can_attack(perm):
            self.pending_attackers.append(uid)
        return self.to_client()

    def action_confirm_attack(self) -> dict:
        """Resolve the player's declared attackers as unblocked damage."""
        assert self.phase == "attack"
        self._fire_attack_triggers(self.pending_attackers)
        for attacker_id in self.pending_attackers:
            perm = self._find_permanent(attacker_id)
            if perm is not None:
                mark_attacked_this_turn(perm)
        result = resolve_combat_damage(
            self.state,
            attacking_player_idx=0,
            defending_player_idx=1,
            attacker_ids=self.pending_attackers,
            blocker_assignments={},
        )
        for attacker_id in self.pending_attackers:
            perm = self._find_permanent(attacker_id)
            if perm is None:
                continue
            frenzy_detail = apply_frenzy_on_unblocked_attack(
                self.state,
                perm,
                blocked=False,
            )
            if frenzy_detail:
                self._log('rules', 'frenzy', frenzy_detail)
                if 'draw' in frenzy_detail:
                    self._draw_cards(perm.controller_idx, 1)
        if result.damage_to_player:
            self._log("player", "attack", f"Attacked for {result.damage_to_player} damage")
        for detail in clear_firebending_mana(self.state, 0):
            self._log('rules', 'firebending', detail)
        for detail in deactivate_living_metal_after_combat(self.state, 0):
            self._log('rules', 'living_metal', detail)
        self.pending_attackers = []
        self.phase = "main2"
        self._check_game_over()
        return self.to_client()

    def action_skip_attack(self) -> dict:
        """Skip combat and move to the second main phase."""
        assert self.phase == "attack"
        for detail in deactivate_living_metal_after_combat(self.state, 0):
            self._log('rules', 'living_metal', detail)
        for detail in clear_firebending_mana(self.state, 0):
            self._log('rules', 'firebending', detail)
        self.pending_attackers = []
        self._log("player", "skip_attack", "Skipped combat")
        self.phase = "main2"
        return self.to_client()

    def action_assign_blocker(self, blocker_uid: str, attacker_uid: str) -> dict:
        """Assign a player creature to block an opponent attacker."""
        assert self.phase == "declare_blockers"
        blocker = self._find_permanent(blocker_uid)
        attacker = self._find_permanent(attacker_uid)
        if (
            blocker is not None
            and attacker is not None
            and blocker.controller_idx == 0
            and attacker.controller_idx == 1
            and legal_blocker(blocker, attacker, self.state)
        ):
            self.pending_blockers[blocker_uid] = attacker_uid
        return self.to_client()

    def action_unassign_blocker(self, blocker_uid: str) -> dict:
        """Remove a blocker assignment."""
        assert self.phase == "declare_blockers"
        self.pending_blockers.pop(blocker_uid, None)
        return self.to_client()

    def action_confirm_blocks(self) -> dict:
        """Resolve opponent combat after blocker assignment."""
        assert self.phase == "declare_blockers"
        for detail in assign_provoke_blocks(
            self.state,
            self.pending_blockers,
            self.pending_opp_attackers,
            defending_player_idx=0,
        ):
            self._log('rules', 'provoke', detail)
        self._fire_block_triggers()
        self._resolve_opponent_combat()
        self._finish_opponent_turn()
        return self.to_client()

    def _log_attack_keyword(self, detail: str | None, tag: str) -> None:
        """Log one on-attack keyword result when it produced a detail."""
        if detail:
            self._log('rules', tag, detail)

    def _apply_permanent_attack_keywords(
        self,
        perm,
        *,
        solo: bool,
        attacker_ids: list[str],
        defending_player_idx: int,
    ) -> None:
        """Apply annihilator through battle cry for one attacking permanent."""
        for apply_fn, tag in (
            (apply_annihilator_on_attack, 'annihilator'),
            (apply_afflict_on_attack, 'afflict'),
            (apply_firebending_on_attack, 'firebending'),
            (apply_double_team_on_attack, 'double team'),
        ):
            self._log_attack_keyword(apply_fn(self.state, perm), tag)
        self._log_attack_keyword(
            apply_exalted_on_attack(self.state, perm, solo_attack=solo),
            'exalted',
        )
        for detail, tag in (
            (apply_mentor_on_attack(self.state, perm, attacker_ids), 'mentor'),
            (apply_training_on_attack(self.state, perm, attacker_ids), 'training'),
        ):
            self._log_attack_keyword(detail, tag)
        self._log_attack_keyword(
            apply_myriad_on_attack(
                self.state,
                perm,
                defending_player_idx=defending_player_idx,
            ),
            'myriad',
        )
        enlist_detail = apply_enlist_on_attack(self.state, perm, attacker_ids)
        self._log_attack_keyword(enlist_detail, 'enlist')
        if enlist_detail and 'draw' in enlist_detail:
            self._draw_cards(perm.controller_idx, 1)
        self._log_attack_keyword(apply_mobilize_on_attack(self.state, perm), 'mobilize')
        self._log_attack_keyword(
            apply_battle_cry_on_attack(self.state, perm, attacker_ids),
            'battle_cry',
        )

    def _apply_attack_keywords(
        self,
        attacker_ids: list[str],
        *,
        defending_player_idx: int,
    ) -> None:
        """Apply annihilator, afflict, mentor, exalted, myriad, and similar on-attack keywords."""
        solo = len(attacker_ids) == 1
        for attacker_id in attacker_ids:
            perm = self._find_permanent(attacker_id)
            if perm is None:
                continue
            self._apply_permanent_attack_keywords(
                perm,
                solo=solo,
                attacker_ids=attacker_ids,
                defending_player_idx=defending_player_idx,
            )

    def _start_opponent_attack(self) -> None:
        """Declare opponent attackers or finish the opponent turn."""
        attackers = eligible_attackers(self._permanents(1))
        if not attackers:
            self._finish_opponent_turn()
            return
        tap_attackers(attackers)
        self.pending_opp_attackers = [str(p.obj_id) for p in attackers]
        self._log("opponent", "attack_declared", f"Attacks with {perm_names(attackers)}")
        self._apply_attack_keywords(self.pending_opp_attackers, defending_player_idx=0)
        self._fire_attack_triggers(self.pending_opp_attackers)
        self.phase = "declare_blockers"

    def _resolve_opponent_combat(self) -> None:
        """Resolve current opponent attackers against assigned blockers."""
        result = resolve_combat_damage(
            self.state,
            attacking_player_idx=1,
            defending_player_idx=0,
            attacker_ids=self.pending_opp_attackers,
            blocker_assignments=self.pending_blockers,
        )
        self._log("opponent", "attack", f"Dealt {result.damage_to_player} damage")
        for detail in clear_firebending_mana(self.state, 1):
            self._log('rules', 'firebending', detail)
        self._check_game_over()

    def _finish_opponent_turn(self) -> None:
        """Clear combat state and move to the player's next draw step."""
        clear_until_end_of_turn_modifiers(self.state)
        self.pending_opp_attackers = []
        self.pending_blockers = {}
        if self._check_game_over():
            return
        self.state.turn.context.turn_number += 1
        self.phase = "draw"

    def _fire_step_triggers(self, step: Step) -> None:
        """Put step-based triggers on the stack and resolve them."""
        self.state.fire_step_triggers(step)
        self._auto_pass_stack()

    def _fire_attack_triggers(self, attacker_ids: list[str]) -> None:
        """Put declared-attacker triggers on the stack and resolve them."""
        attackers = [
            perm
            for attacker_id in attacker_ids
            if (perm := self._find_permanent(attacker_id)) is not None
        ]
        if attackers:
            controller_idx = attackers[0].controller_idx
            attacker_count = len(attackers)
            band_count = attacking_band_size(attackers)
            if band_count >= 2:
                self._log('rules', 'banding', f"band of {band_count} attackers")
            self.state.fire_mass_attack_triggers(
                controller_idx,
                attacker_count,
            )
            for detail in apply_melee_on_mass_attack(
                self.state,
                controller_idx,
                attacker_count,
            ):
                self._log('rules', 'melee', detail)
            defending_player_idx = 1 - controller_idx
            self._apply_attack_keywords(
                attacker_ids,
                defending_player_idx=defending_player_idx,
            )
        for attacker in attackers:
            self.state.fire_attack_triggers(attacker)
        self._auto_pass_stack()

    def _fire_block_triggers(self) -> None:
        """Put declared-blocker triggers on the stack and resolve them."""
        blockers_by_attacker: dict[str, list] = {}
        for blocker_uid, attacker_uid in self.pending_blockers.items():
            blocker = self._find_permanent(blocker_uid)
            attacker = self._find_permanent(attacker_uid)
            if blocker is not None and attacker is not None:
                flank_detail = apply_flanking_on_block(attacker, blocker)
                if flank_detail:
                    self._log('rules', 'flanking', flank_detail)
                band_detail = banding_block_detail(blocker, attacker)
                if band_detail:
                    self._log('rules', 'banding', band_detail)
                self.state.fire_block_triggers(blocker, attacker)
                blockers_by_attacker.setdefault(attacker_uid, []).append(blocker)
        for attacker_uid, blockers in blockers_by_attacker.items():
            attacker = self._find_permanent(attacker_uid)
            if attacker is not None:
                rampage_detail = apply_rampage_on_block(attacker, blockers)
                if rampage_detail:
                    self._log('rules', 'rampage', rampage_detail)
        self._auto_pass_stack()

    def _check_game_over(self) -> bool:
        """Apply SBAs and set game_over phase if a player lost."""
        self.state.check_sbas()
        if self.state.winner is not None:
            self.phase = "game_over"
            return True
        return False
