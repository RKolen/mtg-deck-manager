"""
Phase B interactive game loop built on the rules-engine core.

The public action methods and client payload intentionally match the legacy
`game_engine.InteractiveGame` surface so FastAPI routes and the Gatsby play UI
can be cut over without changing their request/response shapes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine.cards.oracle_parse import is_affordable, spell_category
from engine.core.game_object import CardObject
from engine.core.game_state import GameState
from engine.core.turn_structure import PriorityPassOutcome, Step
from engine.core.zones import Zone
from engine.game.helpers import (
    CastAnnounceOptions,
    card_names,
    is_land,
    payment_requirements,
    perm_names,
    require_card_info,
)
from engine.game.spell_stack import SpellStackMixin
from engine.rules.combat import can_attack, eligible_attackers, legal_blocker
from engine.rules.combat import resolve_combat_damage, tap_attackers


@dataclass
class InteractiveGame(SpellStackMixin):  # pylint: disable=too-many-public-methods
    """Playable two-player game session backed by GameState."""

    state: GameState
    phase: str = "mulligan"
    on_the_play: bool = True
    mulligans_taken: int = 0
    pending_attackers: list[str] = field(default_factory=list)
    pending_opp_attackers: list[str] = field(default_factory=list)
    pending_blockers: dict[str, str] = field(default_factory=dict)

    def action_keep(self) -> dict:
        """Keep the current opening hand and start the first player turn."""
        assert self.phase == "mulligan"
        bottomed = self._bottom_mulligan_cards(0)
        self._log("player", "keep", f"Kept {len(self._zones(0).hand)}-card hand")
        if bottomed:
            self._log("player", "mulligan_bottom", f"Bottomed {card_names(bottomed)}")
        self._start_player_turn_one()
        return self.to_client()

    def action_mulligan(self) -> dict:
        """Shuffle the current hand away and draw seven cards."""
        assert self.phase == "mulligan"
        hand = self._zones(0).hand
        library = self._zones(0).library
        library.extend(hand)
        hand.clear()
        random.shuffle(library)
        self.mulligans_taken += 1
        self._draw_cards(0, 7)
        self._log("player", "mulligan", f"Mulligan {self.mulligans_taken}: drew {len(hand)}")
        return self.to_client()

    def action_draw(self) -> dict:
        """Draw for the player's turn and move to the first main phase."""
        assert self.phase == "draw"
        self._begin_turn(0)
        drawn = self._draw_cards(0, 1)
        self._log("player", "draw", f"Drew: {card_names(drawn) or '-'}")
        self._auto_pass_stack()
        self.phase = "main1"
        return self.to_client()

    def action_play_land(self, hand_idx: int) -> dict:
        """Play a land from the player's hand onto the battlefield."""
        assert self.phase in ("main1", "main2")
        assert not self.state.players[0].land_played
        card = self._zones(0).hand[hand_idx]
        assert isinstance(card, CardObject)
        card_info = require_card_info(card)
        assert card_info.is_land
        self.state.zones.enter_battlefield(card, 0, "play_land", Zone.HAND)
        self.state.players[0].land_played = True
        self._log("player", "land", card_info.name)
        return self.to_client()

    def action_cast(
        self,
        hand_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
        kicker_times: int = 0,
        convoke_creature_ids: list[int] | None = None,
        delve_graveyard_indices: list[int] | None = None,
        improvise_artifact_ids: list[int] | None = None,
    ) -> dict:
        """Cast a spell through the stack, auto-passing while no responses exist."""
        return self._announce_cast(
            hand_idx,
            target_uid,
            target_player,
            auto_resolve=True,
            cast_options=CastAnnounceOptions(
                kicker_times=kicker_times,
                convoke_creature_ids=tuple(convoke_creature_ids or ()),
                delve_graveyard_indices=tuple(delve_graveyard_indices or ()),
                improvise_artifact_ids=tuple(improvise_artifact_ids or ()),
            ),
        )

    def action_cast_to_stack(
        self,
        hand_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
        kicker_times: int = 0,
        convoke_creature_ids: list[int] | None = None,
        delve_graveyard_indices: list[int] | None = None,
        improvise_artifact_ids: list[int] | None = None,
    ) -> dict:
        """Cast a spell and leave it on the stack for explicit priority passes."""
        return self._announce_cast(
            hand_idx,
            target_uid,
            target_player,
            auto_resolve=False,
            cast_options=CastAnnounceOptions(
                kicker_times=kicker_times,
                convoke_creature_ids=tuple(convoke_creature_ids or ()),
                delve_graveyard_indices=tuple(delve_graveyard_indices or ()),
                improvise_artifact_ids=tuple(improvise_artifact_ids or ()),
            ),
        )

    def action_cast_flashback(
        self,
        graveyard_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
    ) -> dict:
        """Cast a card from the graveyard for its flashback cost."""
        return self._announce_flashback_cast(
            graveyard_idx,
            target_uid,
            target_player,
            auto_resolve=True,
        )

    def action_cast_escape(
        self,
        graveyard_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
        escape_exile_indices: list[int] | None = None,
    ) -> dict:
        """Cast a card from the graveyard for its escape cost."""
        return self._announce_escape_cast(
            graveyard_idx,
            target_uid,
            target_player,
            auto_resolve=True,
            escape_exile_indices=escape_exile_indices,
        )

    def action_pass_priority(self) -> dict:
        """Pass priority once; resolve or advance when both players pass."""
        outcome = self.state.turn.pass_priority(self.state.stack.is_empty)
        if outcome == PriorityPassOutcome.RESOLVE_TOP:
            detail = self._resolve_top_of_stack()
            if detail:
                self._log("system", "resolve", detail)
            self.state.turn.priority.reset(self.state.active_player_idx)
            self._check_game_over()
        return self.to_client()

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

    def action_end_turn(self) -> dict:
        """End the player's turn, run a simple opponent turn, then pass back."""
        assert self.phase in ("main1", "main2", "attack")
        self._fire_step_triggers(Step.END_STEP)
        self._log("player", "end_turn", f"End of turn {self.turn}")
        self.phase = "opp_turn"
        self._opponent_main_phase()
        if self.phase != "game_over":
            self._start_opponent_attack()
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

    def full_log(self) -> list[dict]:
        """Return the complete game log."""
        return self._log_to_client()

    def _available_actions(self) -> list[str]:
        """Return action names legal in the current phase."""
        if not self.state.stack.is_empty:
            actions = self._stack_actions()
        elif self.phase == "mulligan":
            actions = ["keep", "mulligan"]
        elif self.phase in ("game_over", "opp_turn"):
            actions = []
        elif self.phase == "draw":
            actions = ["auto_draw"]
        elif self.phase == "declare_blockers":
            actions = self._declare_blockers_actions()
        elif self.phase in ("main1", "main2"):
            actions = self._main_phase_actions()
        elif self.phase == "attack":
            actions = []
            actions.extend(["toggle_attacker", "confirm_attack", "skip_attack"])
            if self._has_castable_instant():
                actions.append("cast_spell")
        else:
            actions = []
        return actions

    def _stack_actions(self) -> list[str]:
        """Return legal actions while the stack is non-empty."""
        actions = ["pass_priority"]
        if self._has_castable_instant():
            actions.append("cast_spell")
        return actions

    def _declare_blockers_actions(self) -> list[str]:
        """Return legal actions in the declare-blockers phase."""
        actions = ["assign_blocker", "unassign_blocker", "confirm_blocks"]
        if self._has_castable_instant():
            actions.append("cast_spell")
        return actions

    def _main_phase_actions(self) -> list[str]:
        """Return legal actions in a main phase with an empty stack."""
        actions: list[str] = []
        player_can_play_land = (
            not self.state.players[0].land_played
            and any(
                isinstance(c, CardObject) and is_land(c) for c in self._zones(0).hand
            )
        )
        if player_can_play_land:
            actions.append("play_land")
        if any(
            isinstance(c, CardObject)
            and not is_land(c)
            and is_affordable(require_card_info(c), self._available_mana(0))
            for c in self._zones(0).hand
        ):
            actions.append("cast_spell")
        if self.phase == "main1":
            actions.append("go_to_attack")
        actions.append("end_turn")
        return actions

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
            perm.tapped = False
            perm.sick = False
            perm.damage_marked = 0
        player = self.state.players[player_idx]
        player.mana_pool.empty()
        player.land_played = False
        player.spells_cast_this_turn = 0
        self._fire_step_triggers(Step.UPKEEP)


    def _opponent_main_phase(self) -> None:
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

    def _opponent_cast_one_spell(self) -> None:
        """Cast the cheapest affordable opponent spell."""
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
        hand_idx, card_info = sorted(
            options,
            key=lambda item: (not item[1].is_creature, item[1].cmc),
        )[0]
        card = self._zones(1).hand[hand_idx]
        if not isinstance(card, CardObject):
            return
        mana_needed, _ = payment_requirements(card_info)
        if not self._tap_lands_for_mana(1, mana_needed):
            return
        target_player = 0 if spell_category(card_info) == "burn" else None
        targets = self._put_spell_on_stack(
            player_idx=1,
            card=card,
            target_uid_str=None,
            target_player_idx=target_player,
        )
        self._log("opponent", "cast", f"{card_info.name} on stack")
        self.state.fire_spell_cast_triggers(card, tuple(targets))
        self._auto_pass_stack()

    def _start_opponent_attack(self) -> None:
        """Declare opponent attackers or finish the opponent turn."""
        attackers = eligible_attackers(self._permanents(1))
        if not attackers:
            self._finish_opponent_turn()
            return
        tap_attackers(attackers)
        self.pending_opp_attackers = [str(p.obj_id) for p in attackers]
        self._log("opponent", "attack_declared", f"Attacks with {perm_names(attackers)}")
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
        for attacker_id in attacker_ids:
            attacker = self._find_permanent(attacker_id)
            if attacker is not None:
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
