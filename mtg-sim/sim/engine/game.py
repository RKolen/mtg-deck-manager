"""
Phase B interactive game loop built on the rules-engine core.

The public action methods and client payload intentionally match the legacy
`game_engine.InteractiveGame` surface so FastAPI routes and the Gatsby play UI
can be cut over without changing their request/response shapes.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field

from deck_registry import CardInfo
from engine.cards.oracle_parse import (
    is_affordable,
    parse_damage,
    parse_draw,
    parse_pump,
    spell_category,
)
from engine.core.game_object import CardObject, Permanent
from engine.core.game_object import SpellOnStack, Target
from engine.core.game_state import GameState, LogEntry, PlayerInfo
from engine.core.turn_structure import PriorityPassOutcome, TurnRunner
from engine.core.zones import Zone, ZoneManager
from engine.rules.stack import Stack


@dataclass
class InteractiveGame:
    """Playable two-player game session backed by GameState."""

    state: GameState
    phase: str = "mulligan"
    on_the_play: bool = True
    pending_attackers: list[str] = field(default_factory=list)
    pending_opp_attackers: list[str] = field(default_factory=list)
    pending_blockers: dict[str, str] = field(default_factory=dict)

    @property
    def turn(self) -> int:
        """Current turn number for the legacy client contract."""
        return self.state.turn.context.turn_number

    @property
    def winner(self) -> int | None:
        """Winning player index, or None while the game is active."""
        return self.state.winner

    def to_client(self) -> dict:
        """Serialise game state using the existing frontend payload shape."""
        return {
            "gameId": self.state.game_id,
            "turn": self.turn,
            "phase": self.phase,
            "winner": self.winner,
            "playerHand": self._hand_to_client(0),
            "playerBattlefield": self._battlefield_to_client(0),
            "playerLife": self.state.players[0].life,
            "playerMana": self._available_mana(0),
            "playerTotalMana": self._total_mana(0),
            "playerLandPlayed": self.state.players[0].land_played,
            "playerGraveyard": self._graveyard_names(0),
            "opponentHandCount": len(self._zones(1).hand),
            "opponentBattlefield": self._battlefield_to_client(1),
            "opponentLife": self.state.players[1].life,
            "opponentMana": self._total_mana(1),
            "opponentGraveyard": self._graveyard_names(1),
            "log": self._log_to_client(limit=20),
            "pendingAttackers": self.pending_attackers,
            "opponentAttackers": [
                p.to_dict() for p in self._permanents(1)
                if str(p.obj_id) in self.pending_opp_attackers
            ],
            "pendingBlockers": self.pending_blockers,
            "stack": self.state.stack.to_client(),
            "availableActions": self._available_actions(),
        }

    def action_keep(self) -> dict:
        """Keep the current opening hand and start the first player turn."""
        assert self.phase == "mulligan"
        self._log("player", "keep", f"Kept {len(self._zones(0).hand)}-card hand")
        self._start_player_turn_one()
        return self.to_client()

    def action_mulligan(self) -> dict:
        """Shuffle the current hand away and draw one fewer card."""
        assert self.phase == "mulligan"
        hand = self._zones(0).hand
        current_size = len(hand)
        if current_size <= 4:
            self._log("player", "keep", f"Forced keep at {current_size} cards")
            self._start_player_turn_one()
            return self.to_client()
        library = self._zones(0).library
        library.extend(hand)
        hand.clear()
        random.shuffle(library)
        self._draw_cards(0, current_size - 1)
        self._log("player", "mulligan", f"Mulligan to {len(hand)}")
        return self.to_client()

    def action_draw(self) -> dict:
        """Draw for the player's turn and move to the first main phase."""
        assert self.phase == "draw"
        self._begin_turn(0)
        drawn = self._draw_cards(0, 1)
        self._log("player", "draw", f"Drew: {_card_names(drawn) or '-'}")
        self.phase = "main1"
        return self.to_client()

    def action_play_land(self, hand_idx: int) -> dict:
        """Play a land from the player's hand onto the battlefield."""
        assert self.phase in ("main1", "main2")
        assert not self.state.players[0].land_played
        card = self._zones(0).hand[hand_idx]
        assert card.card_info is not None and card.card_info.is_land
        self.state.zones.enter_battlefield(card, 0, "play_land", Zone.HAND)
        self.state.players[0].land_played = True
        self._log("player", "land", card.card_info.name)
        return self.to_client()

    def action_cast(
        self,
        hand_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
    ) -> dict:
        """Cast a spell through the stack, auto-passing while no responses exist."""
        return self._announce_cast(hand_idx, target_uid, target_player, auto_resolve=True)

    def action_cast_to_stack(
        self,
        hand_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
    ) -> dict:
        """Cast a spell and leave it on the stack for explicit priority passes."""
        return self._announce_cast(hand_idx, target_uid, target_player, auto_resolve=False)

    def _announce_cast(
        self,
        hand_idx: int,
        target_uid: str | None,
        target_player: int | None,
        auto_resolve: bool,
    ) -> dict:
        """Pay costs and place a spell on the stack."""
        assert self.phase in ("main1", "main2")
        card = self._zones(0).hand[hand_idx]
        card_info = _require_card_info(card)
        assert not card_info.is_land
        mana_needed, life_cost = _payment_requirements(card_info)
        if not self._tap_lands_for_mana(0, mana_needed):
            return {
                **self.to_client(),
                "error": (
                    f"Not enough mana ({self._available_mana(0)} available, "
                    f"need {mana_needed})"
                ),
            }
        self.state.players[0].spells_cast_this_turn += 1
        if life_cost:
            self.state.players[0].life -= life_cost
            self._log("player", "phyrexian", f"Paid {life_cost} life for {card_info.name}")
        self._put_spell_on_stack(
            card,
            target_uid=target_uid,
            target_player=target_player,
        )
        self._log("player", "cast", f"{card_info.name} on stack")
        if auto_resolve:
            self._auto_pass_stack()
        return self.to_client()

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
        if perm is not None and perm.controller_idx == 0 and _can_attack(perm):
            self.pending_attackers.append(uid)
        return self.to_client()

    def action_confirm_attack(self) -> dict:
        """Resolve the player's declared attackers as unblocked damage."""
        assert self.phase == "attack"
        attackers = [p for p in self._permanents(0) if str(p.obj_id) in self.pending_attackers]
        damage = 0
        for attacker in attackers:
            attacker.tapped = True
            damage += _power(attacker)
        if damage:
            self.state.players[1].life -= damage
            self._log("player", "attack", f"Attacked for {damage} damage")
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
        if blocker is not None and attacker is not None and not blocker.tapped:
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
        self._resolve_opponent_combat()
        self._finish_opponent_turn()
        return self.to_client()

    def full_log(self) -> list[dict]:
        """Return the complete game log."""
        return self._log_to_client()

    def _available_actions(self) -> list[str]:
        """Return action names legal in the current phase."""
        if not self.state.stack.is_empty:
            return ["pass_priority"]
        if self.phase == "mulligan":
            return ["keep", "mulligan"]
        if self.phase in ("game_over", "opp_turn"):
            return []
        if self.phase == "draw":
            return ["auto_draw"]
        if self.phase == "declare_blockers":
            return ["assign_blocker", "unassign_blocker", "confirm_blocks"]
        actions: list[str] = []
        if self.phase in ("main1", "main2"):
            player_can_play_land = (
                not self.state.players[0].land_played
                and any(_is_land(c) for c in self._zones(0).hand)
            )
            if player_can_play_land:
                actions.append("play_land")
            if any(is_affordable(_require_card_info(c), self._available_mana(0))
                   for c in self._zones(0).hand if not _is_land(c)):
                actions.append("cast_spell")
            if self.phase == "main1":
                actions.append("go_to_attack")
            actions.append("end_turn")
        if self.phase == "attack":
            actions.extend(["toggle_attacker", "confirm_attack", "skip_attack"])
        return actions

    def _start_player_turn_one(self) -> None:
        """Begin the first player-controlled turn after mulligans."""
        self._begin_turn(0)
        if self.on_the_play:
            self._log("system", "no_draw", "No draw on the play, turn 1")
        else:
            drawn = self._draw_cards(0, 1)
            self._log("player", "draw", f"Drew: {_card_names(drawn) or '-'}")
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

    def _put_spell_on_stack(
        self,
        card: CardObject,
        target_uid: str | None,
        target_player: int | None,
    ) -> None:
        """Move a cast spell from hand to the stack."""
        targets = _targets_from_request(target_uid, target_player)
        self.state.zones.play_from_hand(card, 0)
        self.state.stack.push(SpellOnStack(
            controller_idx=0,
            owner_idx=card.owner_idx,
            source=card,
            targets=targets,
        ))
        self.state.turn.action_taken()

    def _resolve_top_of_stack(self) -> str:
        """Resolve the top stack object and apply its simple Phase B effect."""
        result = self.state.stack.resolve_top(self.state.zones)
        if result.obj is None:
            return ""
        if result.fizzled:
            source = getattr(result.obj, "source", None)
            name = _require_card_info(source).name if isinstance(source, CardObject) else "Object"
            return f"{name} fizzled"
        obj = result.obj
        if isinstance(obj, SpellOnStack) and obj.source is not None:
            return self._apply_spell(obj)
        return "Resolved ability"

    def _apply_spell(self, spell: SpellOnStack) -> str:
        """Apply a resolved spell's effect."""
        card = spell.source
        assert card is not None
        card_info = _require_card_info(card)
        category = spell_category(card_info)
        if category == "creature" and spell.controller_idx == 0:
            self.state.zones.enter_battlefield(card, 0, "resolve")
            return f"Cast creature {card_info.name}"
        if category == "burn" and spell.controller_idx == 0:
            return self._resolve_burn(card, spell.targets)
        if category == "pump" and spell.controller_idx == 0:
            return self._resolve_pump(card, spell.targets)
        if category == "removal" and spell.controller_idx == 0:
            return self._resolve_removal(card, spell.targets)
        if category == "draw" and spell.controller_idx == 0:
            return self._resolve_draw(card)
        self._move_card_to_graveyard(card)
        return f"Cast {card_info.name}"

    def _resolve_burn(
        self,
        card: CardObject,
        targets: list[Target],
    ) -> str:
        card_info = _require_card_info(card)
        damage = parse_damage(card_info.oracle_text or "") or max(1, int(card_info.cmc))
        self._move_card_to_graveyard(card)
        target_player = _target_player(targets)
        target_uid = _target_uid(targets)
        if target_player == 1 or target_uid is None:
            self.state.players[1].life -= damage
            return f"{card_info.name} dealt {damage} damage to opponent"
        target = self._find_permanent(target_uid)
        if target is None:
            return f"Cast {card_info.name} (no valid target)"
        target.damage_marked += damage
        self.state.check_sbas()
        return f"{card_info.name} dealt {damage} damage to {target.name}"

    def _resolve_pump(self, card: CardObject, targets: list[Target]) -> str:
        card_info = _require_card_info(card)
        power, toughness = parse_pump(card_info.oracle_text or "")
        if power == 0 and toughness == 0:
            power, toughness = 1, 1
        target_uid = _target_uid(targets)
        target = self._find_permanent(target_uid) or _last_creature(self._permanents(0))
        self._move_card_to_graveyard(card)
        if target is None:
            return f"Cast {card_info.name} (no target)"
        target.counters["+1/+1"] = target.counters.get("+1/+1", 0) + max(power, toughness)
        return f"{card_info.name} pumped {target.name}"

    def _resolve_removal(self, card: CardObject, targets: list[Target]) -> str:
        card_info = _require_card_info(card)
        self._move_card_to_graveyard(card)
        target_uid = _target_uid(targets)
        target = self._find_permanent(target_uid)
        if target is None:
            return f"Cast {card_info.name} (target not found)"
        self.state.zones.leave_battlefield(target, Zone.GRAVEYARD, "destroy")
        return f"{card_info.name} destroyed {target.name}"

    def _resolve_draw(self, card: CardObject) -> str:
        card_info = _require_card_info(card)
        count = parse_draw(card_info.oracle_text or "") or 1
        drawn = self._draw_cards(0, count)
        self._move_card_to_graveyard(card)
        return f"{card_info.name} drew {_card_names(drawn) or 'no cards'}"

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
            (idx for idx, card in enumerate(self._zones(1).hand) if _is_land(card)),
            None,
        )
        if land_idx is not None:
            card = self._zones(1).hand[land_idx]
            self.state.zones.enter_battlefield(card, 1, "play_land", Zone.HAND)
            self.state.players[1].land_played = True
            self._log("opponent", "land", _require_card_info(card).name)
        self._opponent_cast_one_spell()
        self._check_game_over()

    def _opponent_cast_one_spell(self) -> None:
        """Cast the cheapest affordable opponent spell."""
        options = [
            (idx, _require_card_info(card))
            for idx, card in enumerate(self._zones(1).hand)
            if (
                not _is_land(card)
                and is_affordable(_require_card_info(card), self._available_mana(1))
            )
        ]
        if not options:
            return
        hand_idx, card_info = sorted(
            options,
            key=lambda item: (not item[1].is_creature, item[1].cmc),
        )[0]
        card = self._zones(1).hand[hand_idx]
        mana_needed, _ = _payment_requirements(card_info)
        if not self._tap_lands_for_mana(1, mana_needed):
            return
        self._resolve_opponent_spell(card)

    def _resolve_opponent_spell(self, card: CardObject) -> None:
        """Resolve one simple AI spell."""
        card_info = _require_card_info(card)
        category = spell_category(card_info)
        if category == "creature":
            self.state.zones.enter_battlefield(card, 1, "cast", Zone.HAND)
            self._log("opponent", "cast", card_info.name)
            return
        self.state.zones.play_from_hand(card, 1)
        self._move_card_to_graveyard(card)
        if category == "burn":
            damage = parse_damage(card_info.oracle_text or "") or max(1, int(card_info.cmc))
            self.state.players[0].life -= damage
            self._log("opponent", "burn", f"{card_info.name} dealt {damage} damage to you")
            return
        self._log("opponent", "cast", card_info.name)

    def _start_opponent_attack(self) -> None:
        """Declare opponent attackers or finish the opponent turn."""
        attackers = [p for p in self._permanents(1) if _can_attack(p)]
        if not attackers:
            self._finish_opponent_turn()
            return
        for perm in attackers:
            perm.tapped = True
        self.pending_opp_attackers = [str(p.obj_id) for p in attackers]
        self._log("opponent", "attack_declared", f"Attacks with {_perm_names(attackers)}")
        self.phase = "declare_blockers"

    def _resolve_opponent_combat(self) -> None:
        """Resolve current opponent attackers against assigned blockers."""
        damage_to_player = 0
        attackers = [
            p for p in self._permanents(1)
            if str(p.obj_id) in self.pending_opp_attackers
        ]
        for attacker in attackers:
            blockers = [
                self._find_permanent(blocker_uid)
                for blocker_uid, attacker_uid in self.pending_blockers.items()
                if attacker_uid == str(attacker.obj_id)
            ]
            live_blockers = [b for b in blockers if b is not None]
            if not live_blockers:
                damage_to_player += _power(attacker)
                continue
            blocker = live_blockers[0]
            attacker.damage_marked += _power(blocker)
            blocker.damage_marked += _power(attacker)
        if damage_to_player:
            self.state.players[0].life -= damage_to_player
        self.state.check_sbas()
        self._log("opponent", "attack", f"Dealt {damage_to_player} damage")
        self._check_game_over()

    def _finish_opponent_turn(self) -> None:
        """Clear combat state and move to the player's next draw step."""
        self.pending_opp_attackers = []
        self.pending_blockers = {}
        if self._check_game_over():
            return
        self.state.turn.context.turn_number += 1
        self.phase = "draw"

    def _check_game_over(self) -> bool:
        """Apply SBAs and set game_over phase if a player lost."""
        self.state.check_sbas()
        if self.state.winner is not None:
            self.phase = "game_over"
            return True
        return False

    def _hand_to_client(self, player_idx: int) -> list[dict]:
        """Serialise a player's hand for the existing client contract."""
        available = self._available_mana(player_idx)
        return [
            _card_to_client(idx, _require_card_info(card), available)
            for idx, card in enumerate(self._zones(player_idx).hand)
        ]

    def _battlefield_to_client(self, player_idx: int) -> list[dict]:
        """Serialise a player's battlefield permanents."""
        return [p.to_dict() for p in self._permanents(player_idx)]

    def _graveyard_names(self, player_idx: int) -> list[str]:
        """Return the last few graveyard card names."""
        return [_require_card_info(c).name for c in self._zones(player_idx).graveyard[-5:]]

    def _log_to_client(self, limit: int | None = None) -> list[dict]:
        """Serialise game log entries."""
        entries = self.state.log[-limit:] if limit is not None else self.state.log
        return [
            {"turn": e.turn, "actor": e.actor, "action": e.action, "detail": e.detail}
            for e in entries
        ]

    def _draw_cards(self, player_idx: int, count: int) -> list[CardObject]:
        """Draw up to count cards for a player."""
        drawn = []
        for _ in range(count):
            card = self.state.zones.draw(player_idx)
            if card is not None:
                drawn.append(card)
        return drawn

    def _tap_lands_for_mana(self, player_idx: int, amount: int) -> bool:
        """Tap untapped lands to pay generic mana."""
        lands = self.state.zones.untapped_lands_of(player_idx)
        if len(lands) < amount:
            return False
        for land in lands[:amount]:
            land.tapped = True
        return True

    def _available_mana(self, player_idx: int) -> int:
        return len(self.state.zones.untapped_lands_of(player_idx))

    def _total_mana(self, player_idx: int) -> int:
        return len(self.state.zones.lands_of(player_idx))

    def _permanents(self, player_idx: int) -> list[Permanent]:
        return self.state.zones.permanents_of(player_idx)

    def _zones(self, player_idx: int):
        return self.state.zones.player_zones[player_idx]

    def _find_permanent(self, uid: str | None) -> Permanent | None:
        if uid is None:
            return None
        try:
            return self.state.zones.find_permanent(int(uid))
        except ValueError:
            return None

    def _move_card_to_graveyard(self, card: CardObject) -> None:
        self.state.zones.player_zones[card.owner_idx].graveyard.append(card)

    def _log(self, actor: str, action: str, detail: str = "") -> None:
        self.state.log.append(LogEntry(
            turn=self.turn,
            actor=actor,
            action=action,
            detail=detail,
        ))

    def deal_opening_hands(self) -> None:
        """Draw opening hands for both players."""
        self._draw_cards(0, 7)
        self._draw_cards(1, 7)

    def _auto_pass_stack(self) -> None:
        """Auto-pass both players until the stack is empty."""
        while not self.state.stack.is_empty:
            self.action_pass_priority()
            if not self.state.stack.is_empty:
                self.action_pass_priority()


_sessions: dict[str, InteractiveGame] = {}


def create_game(
    player_cards: list[CardInfo],
    opponent_cards: list[CardInfo],
    player_name: str = "Player",
    opponent_name: str = "Opponent",
    on_the_play: bool = True,
) -> InteractiveGame:
    """Create and register a new interactive game session."""
    zones = ZoneManager()
    zones.player_zones[0].library = _expand_deck(player_cards, 0)
    zones.player_zones[1].library = _expand_deck(opponent_cards, 1)
    random.shuffle(zones.player_zones[0].library)
    random.shuffle(zones.player_zones[1].library)
    runner = TurnRunner()
    runner.begin_turn(0)
    state = GameState(
        game_id=str(uuid.uuid4()),
        zones=zones,
        players=[PlayerInfo(player_name), PlayerInfo(opponent_name)],
        turn=runner,
        stack=Stack(),
    )
    game = InteractiveGame(state=state, on_the_play=on_the_play)
    game.deal_opening_hands()
    _sessions[state.game_id] = game
    return game


def get_game(game_id: str) -> InteractiveGame | None:
    """Retrieve an active game session by ID."""
    return _sessions.get(game_id)


def remove_game(game_id: str) -> None:
    """Remove a game session from the store."""
    _sessions.pop(game_id, None)


def _expand_deck(cards: list[CardInfo], player_idx: int) -> list[CardObject]:
    """Expand CardInfo quantities into CardObjects."""
    result: list[CardObject] = []
    for card in cards:
        if card.sideboard:
            continue
        for _ in range(card.quantity):
            result.append(CardObject(
                controller_idx=player_idx,
                owner_idx=player_idx,
                card_info=card,
            ))
    return result


def _card_to_client(idx: int, card: CardInfo, available_mana: int) -> dict:
    """Serialise one hand card using the existing client shape."""
    return {
        "idx": idx,
        "name": card.name,
        "cmc": card.cmc,
        "type": card.short_type(),
        "power": card.numeric_power,
        "toughness": card.numeric_toughness,
        "oracle": card.oracle_text or "",
        "category": spell_category(card),
        "isLand": card.is_land,
        "isCreature": card.is_creature,
        "affordable": is_affordable(card, available_mana),
    }


def _payment_requirements(card: CardInfo) -> tuple[int, int]:
    """Return mana and life needed for simplified payment."""
    phyrexian_pips = (card.mana_cost or "").upper().count("/P")
    total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
    return max(0, total_cmc - phyrexian_pips), phyrexian_pips * 2


def _require_card_info(card: CardObject) -> CardInfo:
    """Return card_info for a real card object."""
    assert card.card_info is not None
    return card.card_info


def _is_land(card: CardObject) -> bool:
    return _require_card_info(card).is_land


def _targets_from_request(target_uid: str | None, target_player: int | None) -> list[Target]:
    """Convert the legacy action payload target fields to stack targets."""
    targets: list[Target] = []
    if target_uid is not None:
        try:
            targets.append(Target(obj_id=int(target_uid)))
        except ValueError:
            return targets
    if target_player is not None:
        targets.append(Target(player_idx=target_player))
    return targets


def _target_uid(targets: list[Target]) -> str | None:
    """Return the first permanent target as a legacy uid string."""
    target = next((t for t in targets if t.obj_id is not None), None)
    return str(target.obj_id) if target is not None else None


def _target_player(targets: list[Target]) -> int | None:
    """Return the first player target index."""
    target = next((t for t in targets if t.player_idx is not None), None)
    return target.player_idx if target is not None else None


def _can_attack(perm: Permanent) -> bool:
    return "Creature" in perm.type_line and not perm.tapped and not perm.sick


def _power(perm: Permanent) -> int:
    base = perm.card_info.numeric_power if perm.card_info is not None else 0
    return base + perm.counters.get("+1/+1", 0) - perm.counters.get("-1/-1", 0)


def _last_creature(permanents: list[Permanent]) -> Permanent | None:
    creatures = [p for p in permanents if "Creature" in p.type_line]
    return creatures[-1] if creatures else None


def _card_names(cards: list[CardObject]) -> str:
    return ", ".join(_require_card_info(c).name for c in cards)


def _perm_names(permanents: list[Permanent]) -> str:
    return ", ".join(p.name for p in permanents)
