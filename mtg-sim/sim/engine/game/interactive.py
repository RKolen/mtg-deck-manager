"""
Phase B interactive game loop built on the rules-engine core.

The public action methods and client payload intentionally match the legacy
`game_engine.InteractiveGame` surface so FastAPI routes and the Gatsby play UI
can be cut over without changing their request/response shapes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine.abilities import activated
from engine.abilities.activated.bloodrush import can_bloodrush
from engine.abilities.keywords.other.boast import can_boast, clear_boast_turn_counters
from engine.abilities.keywords.other.bushido import clear_bushido_combat_markers
from engine.abilities.keywords.other.craft import has_craft
from engine.abilities.keywords.casting.disturb import can_cast_via_disturb
from engine.abilities.keywords.casting.escape import can_cast_via_escape, escape_exiles_required
from engine.abilities.keywords.casting.flashback import can_cast_via_flashback
from engine.abilities.keywords.casting.harmonize import can_cast_via_harmonize
from engine.abilities.keywords.casting.embalm import can_embalm
from engine.abilities.keywords.other.disguise import can_turn_up_disguise
from engine.abilities.keywords.other.morph import can_turn_up_morph
from engine.abilities.keywords.casting.foretell import (
    can_cast_foretold,
    can_foretell_setup,
    has_foretell,
)
from engine.abilities.keywords.casting.madness import can_cast_via_madness
from engine.abilities.keywords.casting.plot import (
    can_cast_plotted,
    can_plot_setup,
    is_plottable_sorcery,
)
from engine.abilities.keywords.casting.suspend import can_suspend
from engine.abilities.keywords.casting.jump_start import can_cast_via_jump_start, has_jump_start
from engine.abilities.keywords.casting.retrace import can_cast_via_retrace, has_retrace
from engine.abilities.keywords.casting.aftermath import can_cast_aftermath, has_aftermath
from engine.abilities.keywords.other.dredge import apply_dredge, can_dredge_instead_of_draw
from engine.abilities.keywords.other.encore import can_encore
from engine.abilities.keywords.other.eternalize import can_eternalize
from engine.abilities.keywords.other.outlast import can_outlast, clear_outlast_turn_marker
from engine.abilities.keywords.other.ninjutsu import can_ninjutsu
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
    require_card_info,
)
from engine.game.combat_actions import CombatActionsMixin
from engine.game.spell_stack import SpellStackMixin
from mcts import llm_pick
from deck_registry import CardInfo


@dataclass
class InteractiveGame(SpellStackMixin, CombatActionsMixin):
    """Playable two-player game session backed by GameState."""

    state: GameState
    phase: str = "mulligan"
    on_the_play: bool = True
    mulligans_taken: int = 0
    pilot_prompt: str = ""
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

    def action_dredge(self, graveyard_idx: int) -> dict:
        """Replace the draw step draw with dredge."""
        assert self.phase == "draw"
        self._begin_turn(0)
        err, detail, _milled = apply_dredge(self.state.zones, 0, graveyard_idx)
        if err:
            return {**self.to_client(), "error": err}
        self._log("player", "dredge", detail or "dredge")
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
        *,
        cast_options: CastAnnounceOptions | None = None,
    ) -> dict:
        """Cast a spell through the stack, auto-passing while no responses exist."""
        return self._announce_cast(
            hand_idx,
            target_uid,
            target_player,
            auto_resolve=True,
            cast_options=cast_options,
        )

    def action_cast_madness(
        self,
        hand_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
    ) -> dict:
        """Cast a card from hand for its madness cost."""
        return self._announce_madness_cast(
            hand_idx,
            target_uid,
            target_player,
            auto_resolve=True,
        )

    def action_cast_to_stack(
        self,
        hand_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
        *,
        cast_options: CastAnnounceOptions | None = None,
    ) -> dict:
        """Cast a spell and leave it on the stack for explicit priority passes."""
        return self._announce_cast(
            hand_idx,
            target_uid,
            target_player,
            auto_resolve=False,
            cast_options=cast_options,
        )

    def action_cast_disturb(
        self,
        graveyard_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
    ) -> dict:
        """Cast a creature from the graveyard for its disturb cost."""
        return self._announce_disturb_cast(
            graveyard_idx,
            target_uid,
            target_player,
            auto_resolve=True,
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

    def action_cast_harmonize(
        self,
        graveyard_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
        harmonize_creature_ids: list[str] | None = None,
    ) -> dict:
        """Cast a card from the graveyard for its harmonize cost."""
        ids = [int(uid) for uid in (harmonize_creature_ids or [])]
        return self._announce_harmonize_cast(
            graveyard_idx,
            target_uid,
            target_player,
            auto_resolve=True,
            harmonize_creature_ids=ids,
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

    def action_cast_jump_start(
        self,
        graveyard_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
        discard_hand_idx: int | None = None,
    ) -> dict:
        """Cast a card from the graveyard for its jump-start cost."""
        return self._announce_jump_start_cast(
            graveyard_idx,
            target_uid,
            target_player,
            auto_resolve=True,
            discard_hand_idx=discard_hand_idx,
        )

    def action_cast_retrace(
        self,
        graveyard_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
        discard_hand_idx: int | None = None,
    ) -> dict:
        """Cast a card from the graveyard for its mana cost and a discarded land."""
        return self._announce_retrace_cast(
            graveyard_idx,
            target_uid,
            target_player,
            auto_resolve=True,
            discard_hand_idx=discard_hand_idx,
        )

    def action_cast_foretell(
        self,
        exile_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
    ) -> dict:
        """Cast a foretold card from exile for its foretell cost."""
        return self._announce_cast_foretell(
            exile_idx,
            target_uid,
            target_player,
            auto_resolve=True,
        )

    def action_cast_plot(
        self,
        exile_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
    ) -> dict:
        """Cast a plotted sorcery from exile without paying mana."""
        return self._announce_cast_plot(
            exile_idx,
            target_uid,
            target_player,
            auto_resolve=True,
        )

    def action_cast_aftermath(
        self,
        graveyard_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
    ) -> dict:
        """Cast an aftermath card from the graveyard during a main phase."""
        return self._announce_aftermath_cast(
            graveyard_idx,
            target_uid,
            target_player,
            auto_resolve=True,
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

    def action_end_turn(self) -> dict:
        """End the player's turn, run a simple opponent turn, then pass back."""
        assert self.phase in ("main1", "main2", "attack")
        self._fire_step_triggers(Step.END_STEP)
        self._exile_unearth_at_turn_end(0)
        for detail in self._return_dash_creatures_to_hand(0):
            self._log("rules", "dash", detail)
        self._sacrifice_blitz_at_turn_end(0)
        self._sacrifice_decayed_at_turn_end(0)
        self._sacrifice_encore_at_turn_end(0)
        self._log("player", "end_turn", f"End of turn {self.turn}")
        self.phase = "opp_turn"
        self._opponent_main_phase()
        if self.phase != "game_over":
            self._start_opponent_attack()
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
            actions = ["draw"]
            if self._graveyard_can_dredge():
                actions.append("dredge")
        elif self.phase == "declare_blockers":
            actions = self._declare_blockers_actions()
        elif self.phase in ("main1", "main2"):
            actions = self._main_phase_actions()
        elif self.phase == "attack":
            actions = []
            actions.extend(["toggle_attacker", "confirm_attack", "skip_attack"])
            if self._hand_can_ninjutsu():
                actions.append("ninjutsu")
            if self._battlefield_can_boast():
                actions.append("boast")
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
            and is_affordable(
                require_card_info(c),
                self._available_mana(0),
                self.state.zones,
                0,
            )
            for c in self._zones(0).hand
        ):
            actions.append("cast_spell")
        if self._hand_can_cycle():
            actions.append("cycle")
        if self._hand_can_channel():
            actions.append("channel")
        if self._hand_can_bloodrush():
            actions.append("bloodrush")
        if self._hand_can_ninjutsu():
            actions.append("ninjutsu")
        if self._hand_can_embalm():
            actions.append("embalm")
        self._append_delayed_cast_setup_actions(actions)
        self._append_graveyard_cast_actions(actions)
        if self._battlefield_can_craft():
            actions.append("craft")
        if self._battlefield_can_boast():
            actions.append("boast")
        if self._battlefield_can_activate():
            actions.append("activate")
        if self._battlefield_can_outlast():
            actions.append("outlast")
        if self._battlefield_can_turn_up_morph():
            actions.append("turn_up_morph")
        if self.phase == "main1":
            actions.append("go_to_attack")
        actions.append("end_turn")
        return actions

    def _append_delayed_cast_setup_actions(self, actions: list[str]) -> None:
        """Append suspend, foretell, plot, madness, and exile cast actions."""
        if self._hand_can_suspend():
            actions.append("suspend")
        if self._hand_can_foretell():
            actions.append("foretell")
        if self._hand_can_plot():
            actions.append("plot")
        if self._hand_can_madness():
            actions.append("cast_madness")
        if self._exile_can_foretell():
            actions.append("cast_foretell")
        if self._exile_can_plot():
            actions.append("cast_plot")

    def _append_graveyard_cast_actions(self, actions: list[str]) -> None:
        """Append graveyard cast and activation actions for main phase."""
        if self._graveyard_can_unearth():
            actions.append("unearth")
        if self._graveyard_can_scavenge():
            actions.append("scavenge")
        if self._graveyard_can_encore():
            actions.append("encore")
        if self._graveyard_can_eternalize():
            actions.append("eternalize")
        if self._graveyard_can_disturb():
            actions.append("cast_disturb")
        if self._graveyard_can_flashback():
            actions.append("cast_flashback")
        if self._graveyard_can_escape():
            actions.append("cast_escape")
        if self._graveyard_can_jump_start():
            actions.append("cast_jump_start")
        if self._graveyard_can_retrace():
            actions.append("cast_retrace")
        if self._graveyard_can_aftermath():
            actions.append("cast_aftermath")
        if self._graveyard_can_harmonize():
            actions.append("cast_harmonize")

    def _hand_can_cycle(self) -> bool:
        """Return True when a hand card can activate cycling."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and activated.can_cycle(require_card_info(c), self.phase, True)
            for c in self._zones(0).hand
        )

    def _hand_can_channel(self) -> bool:
        """Return True when a hand card can activate channel."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and activated.can_channel(require_card_info(c), self.phase, True)
            for c in self._zones(0).hand
        )

    def _hand_can_bloodrush(self) -> bool:
        """Return True when a hand card can bloodrush."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_bloodrush(require_card_info(c), self.phase, True)
            for c in self._zones(0).hand
        )

    def _hand_can_ninjutsu(self) -> bool:
        """Return True when a hand card can use ninjutsu."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_ninjutsu(require_card_info(c), self.phase, True)
            for c in self._zones(0).hand
        )

    def _hand_can_embalm(self) -> bool:
        """Return True when a hand creature can activate embalm."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_embalm(require_card_info(c), self.phase, True)
            for c in self._zones(0).hand
        )

    def _hand_can_suspend(self) -> bool:
        """Return True when a hand card can be suspended."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_suspend(require_card_info(c), self.phase, True)
            for c in self._zones(0).hand
        )

    def _hand_can_foretell(self) -> bool:
        """Return True when a hand card can be foretold."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and has_foretell(require_card_info(c))
            and can_foretell_setup(self.phase, True)
            for c in self._zones(0).hand
        )

    def _hand_can_plot(self) -> bool:
        """Return True when a hand sorcery can be plotted."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and is_plottable_sorcery(require_card_info(c))
            and can_plot_setup(self.phase, True)
            for c in self._zones(0).hand
        )

    def _hand_can_madness(self) -> bool:
        """Return True when a hand card can be cast for madness."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_cast_via_madness(require_card_info(c), self.phase, True)
            for c in self._zones(0).hand
        )

    def _exile_can_foretell(self) -> bool:
        """Return True when a foretold card in exile can be cast."""
        if not self.state.stack.is_empty:
            return False
        for card in self._zones(0).exile:
            if not isinstance(card, CardObject) or card.card_info is None:
                continue
            if card.exiled_cast_mode != 'foretell':
                continue
            if can_cast_foretold(card.card_info, self.phase, True):
                return True
        return False

    def _exile_can_plot(self) -> bool:
        """Return True when a plotted card in exile can be cast."""
        if not self.state.stack.is_empty:
            return False
        for card in self._zones(0).exile:
            if not isinstance(card, CardObject) or card.card_info is None:
                continue
            if card.exiled_cast_mode != 'plot':
                continue
            if can_cast_plotted(card.card_info, self.phase, True):
                return True
        return False

    def _graveyard_can_unearth(self) -> bool:
        """Return True when a graveyard card can be unearthed."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and activated.can_unearth(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_encore(self) -> bool:
        """Return True when a graveyard creature can be given encore."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_encore(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_eternalize(self) -> bool:
        """Return True when a graveyard creature can be eternalized."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_eternalize(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_disturb(self) -> bool:
        """Return True when a graveyard creature can be cast for disturb."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_cast_via_disturb(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_flashback(self) -> bool:
        """Return True when a graveyard card can be cast for flashback."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_cast_via_flashback(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_harmonize(self) -> bool:
        """Return True when a graveyard card can be cast for harmonize."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and can_cast_via_harmonize(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_escape(self) -> bool:
        """Return True when a graveyard card can be cast for escape."""
        if not self.state.stack.is_empty:
            return False
        graveyard = self._zones(0).graveyard
        return any(
            isinstance(c, CardObject)
            and can_cast_via_escape(require_card_info(c), self.phase, True)
            and len(graveyard) > escape_exiles_required(require_card_info(c))
            for c in graveyard
        )

    def _graveyard_can_dredge(self) -> bool:
        """Return True when a graveyard card can replace the draw step."""
        if self.phase != "draw":
            return False
        return any(
            isinstance(c, CardObject)
            and can_dredge_instead_of_draw(require_card_info(c), self.phase)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_scavenge(self) -> bool:
        """Return True when a graveyard creature can scavenge."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and activated.can_scavenge(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_jump_start(self) -> bool:
        """Return True when a graveyard card can be cast for jump-start."""
        if not self.state.stack.is_empty:
            return False
        hand = self._zones(0).hand
        if not hand:
            return False
        return any(
            isinstance(c, CardObject)
            and has_jump_start(require_card_info(c))
            and can_cast_via_jump_start(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_retrace(self) -> bool:
        """Return True when a graveyard card can be cast for retrace."""
        if not self.state.stack.is_empty:
            return False
        hand = self._zones(0).hand
        if not any(isinstance(c, CardObject) and is_land(c) for c in hand):
            return False
        return any(
            isinstance(c, CardObject)
            and has_retrace(require_card_info(c))
            and can_cast_via_retrace(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _graveyard_can_aftermath(self) -> bool:
        """Return True when a graveyard card can be cast for aftermath."""
        if not self.state.stack.is_empty:
            return False
        return any(
            isinstance(c, CardObject)
            and has_aftermath(require_card_info(c))
            and can_cast_aftermath(require_card_info(c), self.phase, True)
            for c in self._zones(0).graveyard
        )

    def _battlefield_can_craft(self) -> bool:
        """Return True when a permanent with craft is on the battlefield."""
        if not self.state.stack.is_empty:
            return False
        return any(has_craft(perm) for perm in self._permanents(0))

    def _battlefield_can_outlast(self) -> bool:
        """Return True when a creature can activate outlast."""
        if not self.state.stack.is_empty:
            return False
        return any(can_outlast(perm, self.state, 0, self.phase) for perm in self._permanents(0))

    def _battlefield_can_turn_up_morph(self) -> bool:
        """Return True when a face-down morph or disguise creature can turn face up."""
        if not self.state.stack.is_empty:
            return False
        return any(
            can_turn_up_morph(perm, self.state, 0, self.phase)
            or can_turn_up_disguise(perm, self.state, 0, self.phase)
            for perm in self._permanents(0)
        )

    def _battlefield_can_boast(self) -> bool:
        """Return True when an attacking creature can boast."""
        if not self.state.stack.is_empty:
            return False
        if self.phase == "attack":
            for uid in self.pending_attackers:
                perm = self._find_permanent(uid)
                if perm is not None and can_boast(perm, self.phase, is_attacking=True):
                    return True
            return False
        return any(
            can_boast(perm, self.phase)
            for perm in self._permanents(0)
        )

    def _battlefield_can_activate(self) -> bool:
        """Return True when a permanent has a legal non-mana activation."""
        speed = (
            activated.ActivationSpeed.INSTANT
            if self.phase in ("attack", "declare_blockers") or not self.state.stack.is_empty
            else activated.ActivationSpeed.SORCERY
        )
        for perm in self._permanents(0):
            specs = activated.parse_activated_abilities(perm.oracle_text)
            for spec in specs:
                if spec.mana_ability or spec.equip:
                    continue
                if activated.can_activate(perm, spec, self.state, 0, speed):
                    return True
        return False

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
        self._fire_step_triggers(Step.UPKEEP)
        self._tick_suspend_upkeep(player_idx)


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

    def _llm_pick_spell(
        self,
        options: list[tuple[int, CardInfo]],
    ) -> tuple[int, CardInfo]:
        """Pick the best spell to cast from available options.

        Uses the LLM with the archetype pilot prompt when available, falling
        back to the cheapest-creature-first heuristic when no pilot prompt is
        configured or Ollama is unreachable.
        """
        heuristic = sorted(
            options,
            key=lambda item: (not item[1].is_creature, item[1].cmc),
        )[0]
        if not self.pilot_prompt:
            return heuristic
        option_names = [
            f"{ci.name} ({ci.short_type()}, CMC {int(ci.cmc)})"
            for _, ci in options
        ]
        state = {
            "turn": self.state.turn.context.turn_number,
            "own_life": self.state.players[1].life,
            "opp_life": self.state.players[0].life,
            "mana": self._available_mana(1),
        }
        idx, reasoning = llm_pick(
            "Choose the ONE spell to cast that best serves your archetype strategy.",
            option_names,
            state,
            system_prompt=self.pilot_prompt,
        )
        if reasoning:
            self._log("pilot", "pick", reasoning)
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
        hand_idx, card_info = self._llm_pick_spell(options)
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
