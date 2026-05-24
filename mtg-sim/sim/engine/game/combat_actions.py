"""Player combat actions and combat-phase helpers for InteractiveGame."""

from __future__ import annotations

from engine.abilities.keywords.other.afflict import apply_afflict_on_attack
from engine.abilities.keywords.other.boast import mark_attacked_this_turn
from engine.abilities.keywords.other.enlist import apply_enlist_on_attack
from engine.abilities.keywords.other.myriad import apply_myriad_on_attack
from engine.abilities.keywords.other.annihilator import apply_annihilator_on_attack
from engine.abilities.keywords.other.exalted import apply_exalted_on_attack
from engine.abilities.keywords.other.mentor import apply_mentor_on_attack
from engine.core.turn_structure import Step
from engine.game.activated_actions import ActivatedActionsMixin
from engine.game.helpers import perm_names
from engine.rules.combat import (
    can_attack,
    eligible_attackers,
    legal_blocker,
    resolve_combat_damage,
    tap_attackers,
)


class CombatActionsMixin(ActivatedActionsMixin):
    """Attack and block steps for the human player."""

    def action_go_to_attack(self) -> dict:
        """Move from first main phase to declare attackers."""
        assert self.phase == "main1"
        self._fire_step_triggers(Step.BEGIN_COMBAT)
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
        if result.damage_to_player:
            self._log("player", "attack", f"Attacked for {result.damage_to_player} damage")
        self.pending_attackers = []
        self.phase = "main2"
        self._check_game_over()
        return self.to_client()

    def action_skip_attack(self) -> dict:
        """Skip combat and move to the second main phase."""
        assert self.phase == "attack"
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
        self._fire_block_triggers()
        self._resolve_opponent_combat()
        self._finish_opponent_turn()
        return self.to_client()

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
            for apply_fn, tag in (
                (apply_annihilator_on_attack, 'annihilator'),
                (apply_afflict_on_attack, 'afflict'),
            ):
                detail = apply_fn(self.state, perm)
                if detail:
                    self._log('rules', tag, detail)
            exalted_detail = apply_exalted_on_attack(
                self.state,
                perm,
                solo_attack=solo,
            )
            if exalted_detail:
                self._log('rules', 'exalted', exalted_detail)
            mentor_detail = apply_mentor_on_attack(
                self.state,
                perm,
                attacker_ids,
            )
            if mentor_detail:
                self._log('rules', 'mentor', mentor_detail)
            myriad_detail = apply_myriad_on_attack(
                self.state,
                perm,
                defending_player_idx=defending_player_idx,
            )
            if myriad_detail:
                self._log('rules', 'myriad', myriad_detail)
            enlist_detail = apply_enlist_on_attack(
                self.state,
                perm,
                attacker_ids,
            )
            if enlist_detail:
                self._log('rules', 'enlist', enlist_detail)
                if 'draw' in enlist_detail:
                    self._draw_cards(perm.controller_idx, 1)

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
        self._check_game_over()

    def _finish_opponent_turn(self) -> None:
        """Clear combat state and move to the player's next draw step."""
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
            self.state.fire_mass_attack_triggers(
                attackers[0].controller_idx,
                len(attackers),
            )
            defending_player_idx = 1 - attackers[0].controller_idx
            self._apply_attack_keywords(
                attacker_ids,
                defending_player_idx=defending_player_idx,
            )
        for attacker in attackers:
            self.state.fire_attack_triggers(attacker)
        self._auto_pass_stack()

    def _fire_block_triggers(self) -> None:
        """Put declared-blocker triggers on the stack and resolve them."""
        for blocker_uid, attacker_uid in self.pending_blockers.items():
            blocker = self._find_permanent(blocker_uid)
            attacker = self._find_permanent(attacker_uid)
            if blocker is not None and attacker is not None:
                self.state.fire_block_triggers(blocker, attacker)
        self._auto_pass_stack()

    def _check_game_over(self) -> bool:
        """Apply SBAs and set game_over phase if a player lost."""
        self.state.check_sbas()
        if self.state.winner is not None:
            self.phase = "game_over"
            return True
        return False
