"""
Interactive MTG game engine — player vs. AI archetype.

The human player controls their deck, makes real decisions turn by turn.
The AI opponent plays the meta archetype automatically.
Each completed game is saved as a structured log for simulation calibration.

Phases per player turn:
  draw → main1 (play land, cast spells) → attack → main2 (cast spells) → end_turn

Simplifications vs. full rules:
- No stack / instant-speed responses
- Auto-tap mana (generic; all lands produce 1 mana)
- Damage clears at end of turn
- No triggered abilities beyond basic heroic/prowess approximation
- Spell effects resolved via oracle-text parsing (damage, pump, draw, removal)
"""

from __future__ import annotations

import logging
import random
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from deck_registry import CardInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Oracle text helpers
# ---------------------------------------------------------------------------

def _parse_damage(text: str) -> int:
    m = re.search(r"deals? (\d+) damage", text, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _parse_pump(text: str) -> tuple[int, int]:
    m = re.search(r"gets? \+(\d+)/\+(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"base power and toughness (\d+)/(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def _parse_draw(text: str) -> int:
    m = re.search(r"draw (\w+) card", text, re.IGNORECASE)
    if not m:
        return 0
    w = m.group(1).lower()
    return {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3}.get(w, int(w) if w.isdigit() else 1)


def _spell_category(card: "CardInfo") -> str:
    t = (card.oracle_text or "").lower()
    if card.is_land:
        return "land"
    if card.is_creature:
        return "creature"
    if "deals" in t and "damage" in t:
        return "burn"
    if "+1/+1" in t or re.search(r"gets? \+\d/\+\d", t):
        return "pump"
    if "destroy" in t or "exile" in t:
        return "removal"
    if "draw" in t and "card" in t:
        return "draw"
    if "enchant " in t:
        return "aura"
    return "spell"


# ---------------------------------------------------------------------------
# In-play card representation
# ---------------------------------------------------------------------------

@dataclass
class Permanent:
    uid: str
    card: "CardInfo"
    tapped: bool = False
    sick: bool = True
    power_bonus: int = 0
    toughness_bonus: int = 0
    damage: int = 0
    counters: dict[str, int] = field(default_factory=dict)

    @property
    def effective_power(self) -> int:
        return max(0, self.card.numeric_power + self.power_bonus
                   + self.counters.get("+1/+1", 0))

    @property
    def effective_toughness(self) -> int:
        return max(1, self.card.numeric_toughness + self.toughness_bonus
                   + self.counters.get("+1/+1", 0))

    def can_attack(self) -> bool:
        has_haste = "haste" in (self.card.oracle_text or "").lower()
        return not self.tapped and (not self.sick or has_haste) and self.card.is_creature

    def is_dead(self) -> bool:
        return self.damage >= self.effective_toughness

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "name": self.card.name,
            "cmc": self.card.cmc,
            "type": self.card.short_type(),
            "power": self.effective_power,
            "toughness": self.effective_toughness,
            "tapped": self.tapped,
            "sick": self.sick and "haste" not in (self.card.oracle_text or "").lower(),
            "canAttack": self.can_attack(),
            "oracle": self.card.oracle_text or "",
            "counters": self.counters,
        }


def _new_permanent(card: "CardInfo") -> Permanent:
    return Permanent(uid=str(uuid.uuid4())[:8], card=card)


# ---------------------------------------------------------------------------
# Player state
# ---------------------------------------------------------------------------

@dataclass
class PlayerState:
    name: str
    library: list["CardInfo"]
    hand: list["CardInfo"] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    graveyard: list["CardInfo"] = field(default_factory=list)
    life: int = 20
    mana_spent: int = 0
    land_played: bool = False
    spells_cast_this_turn: int = 0

    def available_mana(self) -> int:
        lands = sum(1 for p in self.battlefield if p.card.is_land and not p.tapped)
        return max(0, lands - self.mana_spent)

    def total_mana(self) -> int:
        return sum(1 for p in self.battlefield if p.card.is_land)

    def creatures(self) -> list[Permanent]:
        return [p for p in self.battlefield if p.card.is_creature]

    def lands(self) -> list[Permanent]:
        return [p for p in self.battlefield if p.card.is_land]

    def draw(self, n: int = 1) -> list["CardInfo"]:
        drawn = self.library[:n]
        self.library = self.library[n:]
        self.hand.extend(drawn)
        return drawn

    def tap_mana(self, amount: int) -> bool:
        available = self.total_mana() - self.mana_spent
        if available < amount:
            return False
        self.mana_spent += amount
        return True

    def begin_turn(self) -> None:
        for p in self.battlefield:
            p.tapped = False
            p.sick = False
            p.power_bonus = 0
            p.toughness_bonus = 0
            p.damage = 0
        self.mana_spent = 0
        self.land_played = False
        self.spells_cast_this_turn = 0

    def hand_to_dict(self) -> list[dict]:
        return [
            {
                "idx": i,
                "name": c.name,
                "cmc": c.cmc,
                "type": c.short_type(),
                "power": c.numeric_power,
                "toughness": c.numeric_toughness,
                "oracle": c.oracle_text or "",
                "category": _spell_category(c),
                "isLand": c.is_land,
                "isCreature": c.is_creature,
            }
            for i, c in enumerate(self.hand)
        ]


# ---------------------------------------------------------------------------
# Game log entry
# ---------------------------------------------------------------------------

@dataclass
class LogEntry:
    turn: int
    actor: str   # "player" | "opponent"
    action: str
    detail: str = ""


# ---------------------------------------------------------------------------
# Interactive game
# ---------------------------------------------------------------------------

PHASES = ["mulligan", "draw", "main1", "attack", "main2", "end", "opp_turn", "game_over"]


@dataclass
class InteractiveGame:
    game_id: str
    player: PlayerState
    opponent: PlayerState
    turn: int = 1
    phase: str = "mulligan"
    winner: Optional[int] = None   # 0=player, 1=opponent
    log: list[LogEntry] = field(default_factory=list)
    pending_attackers: list[str] = field(default_factory=list)  # Permanent uids

    # -------------------------------------------------------------------------
    # Serialisation
    # -------------------------------------------------------------------------

    def to_client(self) -> dict:
        """Full game state for the frontend (opponent hand hidden)."""
        return {
            "gameId": self.game_id,
            "turn": self.turn,
            "phase": self.phase,
            "winner": self.winner,
            "playerHand": self.player.hand_to_dict(),
            "playerBattlefield": [p.to_dict() for p in self.player.battlefield],
            "playerLife": self.player.life,
            "playerMana": self.player.total_mana() - self.player.mana_spent,
            "playerTotalMana": self.player.total_mana(),
            "playerLandPlayed": self.player.land_played,
            "playerGraveyard": [c.name for c in self.player.graveyard[-5:]],
            "opponentHandCount": len(self.opponent.hand),
            "opponentBattlefield": [p.to_dict() for p in self.opponent.battlefield],
            "opponentLife": self.opponent.life,
            "opponentMana": self.opponent.total_mana(),
            "opponentGraveyard": [c.name for c in self.opponent.graveyard[-5:]],
            "log": [{"turn": e.turn, "actor": e.actor, "action": e.action, "detail": e.detail}
                    for e in self.log[-20:]],
            "pendingAttackers": self.pending_attackers,
            "availableActions": self._available_actions(),
        }

    def _available_actions(self) -> list[str]:
        if self.phase == "mulligan":
            return ["keep", "mulligan"]
        if self.phase in ("game_over", "opp_turn"):
            return []
        if self.phase == "draw":
            return ["auto_draw"]
        actions = []
        if self.phase in ("main1", "main2"):
            if not self.player.land_played:
                actions.append("play_land")
            actions.append("cast_spell")
            if self.phase == "main1":
                actions.append("go_to_attack")
            actions.append("end_turn")
        if self.phase == "attack":
            actions.append("toggle_attacker")
            actions.append("confirm_attack")
            actions.append("skip_attack")
        return actions

    # -------------------------------------------------------------------------
    # Player actions
    # -------------------------------------------------------------------------

    def action_keep(self) -> dict:
        assert self.phase == "mulligan"
        self._log("player", "keep", f"Kept {len(self.player.hand)}-card hand")
        self.phase = "draw"
        return self.to_client()

    def action_mulligan(self) -> dict:
        assert self.phase == "mulligan"
        current = len(self.player.hand)
        if current <= 4:
            self._log("player", "keep", f"Forced keep at {current} cards")
            self.phase = "draw"
            return self.to_client()
        # Put hand back, reshuffle, draw one fewer
        self.player.library = self.player.hand + self.player.library
        random.shuffle(self.player.library)
        self.player.hand = []
        self.player.draw(current - 1)
        self._log("player", "mulligan", f"Mulligan to {len(self.player.hand)}")
        return self.to_client()

    def action_draw(self) -> dict:
        """Start of turn draw."""
        assert self.phase == "draw"
        drawn = self.player.draw(1)
        name = drawn[0].name if drawn else "—"
        self._log("player", "draw", f"Drew: {name}")
        self.player.begin_turn()
        self.phase = "main1"
        return self.to_client()

    def action_play_land(self, hand_idx: int) -> dict:
        assert self.phase in ("main1", "main2")
        assert not self.player.land_played
        card = self.player.hand.pop(hand_idx)
        assert card.is_land
        self.player.battlefield.append(_new_permanent(card))
        self.player.land_played = True
        self.player.mana_spent = 0  # refresh pool with new land
        self._log("player", "land", card.name)
        return self.to_client()

    def action_cast(self, hand_idx: int, target_uid: Optional[str] = None,
                    target_player: Optional[int] = None) -> dict:
        """Cast a spell from hand. Resolves effect immediately (no stack)."""
        assert self.phase in ("main1", "main2")
        card = self.player.hand[hand_idx]
        assert not card.is_land

        cost = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
        if not self.player.tap_mana(cost):
            return {**self.to_client(), "error": f"Not enough mana ({self.player.total_mana() - self.player.mana_spent} available, need {cost})"}

        self.player.hand.pop(hand_idx)
        self.player.spells_cast_this_turn += 1

        # Prowess: +1/+1 to each creature with prowess until EOT
        for p in self.player.creatures():
            if "prowess" in (p.card.oracle_text or "").lower():
                p.power_bonus += 1
                p.toughness_bonus += 1

        category = _spell_category(card)
        detail = f"Cast {card.name}"

        if category == "creature":
            perm = _new_permanent(card)
            self.player.battlefield.append(perm)
            # Heroic on self if targeted by another spell (handled externally)
            detail = f"Cast creature {card.name} ({card.numeric_power}/{card.numeric_toughness})"

        elif category == "burn":
            dmg = _parse_damage(card.oracle_text or "")
            if dmg == 0:
                dmg = max(1, int(card.cmc))  # fallback
            if target_player == 1 or target_uid is None:
                self.opponent.life -= dmg
                detail = f"{card.name} → {dmg} damage to opponent (life: {self.opponent.life})"
                self._log("player", "burn", detail)
            else:
                perm = self._find_permanent(self.opponent.battlefield, target_uid)
                if perm:
                    perm.damage += dmg
                    detail = f"{card.name} → {dmg} damage to {perm.card.name}"
                    self._remove_dead(self.opponent)
            self.player.graveyard.append(card)

        elif category == "pump":
            pp, pt = _parse_pump(card.oracle_text or "")
            if pp == 0 and pt == 0:
                pp, pt = 1, 1
            target = self._find_permanent(self.player.battlefield, target_uid)
            if target is None and self.player.creatures():
                target = self.player.creatures()[-1]
            if target:
                if "base power and toughness" in (card.oracle_text or "").lower():
                    target.power_bonus = pp - target.card.numeric_power
                    target.toughness_bonus = pt - target.card.numeric_toughness
                else:
                    target.power_bonus += pp
                    target.toughness_bonus += pt
                # Heroic trigger
                if "heroic" in (target.card.oracle_text or "").lower():
                    target.counters["+1/+1"] = target.counters.get("+1/+1", 0) + 1
                detail = f"{card.name} → {target.card.name} gets +{pp}/+{pt}"
            self.player.graveyard.append(card)

        elif category == "removal":
            if target_uid:
                perm = self._find_permanent(self.opponent.battlefield, target_uid)
                if perm:
                    self.opponent.battlefield.remove(perm)
                    self.opponent.graveyard.append(perm.card)
                    detail = f"{card.name} → destroyed {perm.card.name}"
            self.player.graveyard.append(card)

        elif category == "draw":
            n = _parse_draw(card.oracle_text or "") or 1
            drawn = self.player.draw(n)
            detail = f"{card.name} → drew {', '.join(c.name for c in drawn)}"
            self.player.graveyard.append(card)

        elif category == "aura":
            perm = _new_permanent(card)
            perm.sick = False
            self.player.battlefield.append(perm)
            # Apply pump if aura has it
            pp, pt = _parse_pump(card.oracle_text or "")
            if pp or pt:
                target = self._find_permanent(self.player.battlefield, target_uid)
                if target:
                    target.power_bonus += pp
                    target.toughness_bonus += pt
                    detail = f"Enchanted {target.card.name} with {card.name}"

        else:
            self.player.graveyard.append(card)

        self._log("player", "cast", detail)
        if self._check_game_over():
            return self.to_client()
        return self.to_client()

    def action_go_to_attack(self) -> dict:
        assert self.phase == "main1"
        self.phase = "attack"
        self.pending_attackers = []
        return self.to_client()

    def action_toggle_attacker(self, uid: str) -> dict:
        assert self.phase == "attack"
        if uid in self.pending_attackers:
            self.pending_attackers.remove(uid)
        else:
            perm = self._find_permanent(self.player.battlefield, uid)
            if perm and perm.can_attack():
                self.pending_attackers.append(uid)
        return self.to_client()

    def action_confirm_attack(self) -> dict:
        assert self.phase == "attack"
        attackers = [p for p in self.player.battlefield
                     if p.uid in self.pending_attackers]
        if attackers:
            damage = self._resolve_combat(attackers, self.opponent)
            self._log("player", "attack",
                      f"Attacked with {[a.card.name for a in attackers]} → {damage} damage to opponent (life: {self.opponent.life})")
        self.pending_attackers = []
        self.phase = "main2"
        if self._check_game_over():
            return self.to_client()
        return self.to_client()

    def action_skip_attack(self) -> dict:
        assert self.phase == "attack"
        self.pending_attackers = []
        self._log("player", "skip_attack", "Skipped combat")
        self.phase = "main2"
        return self.to_client()

    def action_end_turn(self) -> dict:
        assert self.phase in ("main1", "main2", "attack")
        self._log("player", "end_turn", f"End of turn {self.turn}")
        self.phase = "opp_turn"
        self._opponent_full_turn()
        if self._check_game_over():
            return self.to_client()
        self.turn += 1
        self.phase = "draw"
        return self.to_client()

    # -------------------------------------------------------------------------
    # Opponent (AI) full turn
    # -------------------------------------------------------------------------

    def _opponent_full_turn(self) -> dict:
        opp = self.opponent
        opp.begin_turn()

        # Draw
        drawn = opp.draw(1)
        if drawn:
            self._log("opponent", "draw", f"Drew a card ({len(opp.hand)} in hand)")

        # Play land
        land = next((c for c in opp.hand if c.is_land), None)
        if land and not opp.land_played:
            opp.hand.remove(land)
            opp.battlefield.append(_new_permanent(land))
            opp.land_played = True
            self._log("opponent", "land", land.name)

        # Cast spells (cheapest first, creatures prioritised)
        mana_available = opp.total_mana()
        mana_spent = 0
        castable = sorted(
            [c for c in opp.hand if not c.is_land and c.cmc <= mana_available - mana_spent],
            key=lambda c: (not c.is_creature, c.cmc),
        )
        for card in castable:
            cost = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
            if mana_spent + cost > mana_available:
                continue
            opp.hand.remove(card)
            mana_spent += cost
            category = _spell_category(card)
            if category == "creature":
                perm = _new_permanent(card)
                opp.battlefield.append(perm)
                self._log("opponent", "cast", f"{card.name} ({card.numeric_power}/{card.numeric_toughness})")
            elif category == "burn":
                dmg = _parse_damage(card.oracle_text or "") or max(1, int(card.cmc))
                # AI burns the player
                self.player.life -= dmg
                opp.graveyard.append(card)
                self._log("opponent", "burn", f"{card.name} → {dmg} damage to you (your life: {self.player.life})")
            elif category == "removal":
                # Remove your biggest creature
                targets = sorted(self.player.creatures(), key=lambda p: -p.effective_power)
                if targets:
                    victim = targets[0]
                    self.player.battlefield.remove(victim)
                    self.player.graveyard.append(victim.card)
                    opp.graveyard.append(card)
                    self._log("opponent", "removal", f"{card.name} → destroyed your {victim.card.name}")
                else:
                    opp.graveyard.append(card)
            elif category == "pump":
                # Pump its biggest attacker
                targets = sorted(opp.creatures(), key=lambda p: -p.effective_power)
                if targets:
                    pp, pt = _parse_pump(card.oracle_text or "")
                    targets[0].power_bonus += pp
                    targets[0].toughness_bonus += pt
                opp.graveyard.append(card)
                self._log("opponent", "cast", f"{card.name}")
            else:
                opp.graveyard.append(card)
                self._log("opponent", "cast", f"{card.name}")

            if self._check_game_over():
                return self.to_client()

        # Attack — all non-sick creatures
        attackers = [p for p in opp.creatures() if p.can_attack()]
        if attackers:
            damage = self._resolve_combat(attackers, self.player,
                                          defender_side=self.player)
            self._log("opponent", "attack",
                      f"Attacked with {[a.card.name for a in attackers]} → {damage} damage (your life: {self.player.life})")
            if self._check_game_over():
                return self.to_client()

        # Mark new creatures as no longer sick for opponent's side
        for p in opp.battlefield:
            p.sick = False

        return self.to_client()

    # -------------------------------------------------------------------------
    # Combat resolution
    # -------------------------------------------------------------------------

    def _resolve_combat(self, attackers: list[Permanent],
                        defender_state: PlayerState,
                        defender_side: Optional[PlayerState] = None) -> int:
        """
        Optimal blocking: defender blocks with creatures to minimise damage,
        preferring to block the largest threats first.
        Returns damage dealt to the defending player.
        """
        if defender_side is None:
            defender_side = self.opponent

        blockers = sorted(
            [p for p in defender_side.creatures() if not p.tapped],
            key=lambda p: p.effective_toughness,
            reverse=True,
        )
        sorted_attackers = sorted(attackers, key=lambda p: -p.effective_power)

        damage_through = 0
        for atk in sorted_attackers:
            atk.tapped = True
            if blockers:
                blk = blockers.pop(0)
                # First-strike / trample simplified: just deal damage both ways
                atk.damage += blk.effective_power
                blk.damage += atk.effective_power
                if blk.is_dead():
                    if blk in defender_side.battlefield:
                        defender_side.battlefield.remove(blk)
                        defender_side.graveyard.append(blk.card)
                if atk.is_dead():
                    if atk in self.player.battlefield:
                        self.player.battlefield.remove(atk)
                        self.player.graveyard.append(atk.card)
                    elif atk in self.opponent.battlefield:
                        self.opponent.battlefield.remove(atk)
                        self.opponent.graveyard.append(atk.card)
            else:
                damage_through += atk.effective_power

        defender_state.life -= damage_through
        return damage_through

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _log(self, actor: str, action: str, detail: str = "") -> None:
        self.log.append(LogEntry(turn=self.turn, actor=actor, action=action, detail=detail))
        logger.debug("T%d [%s] %s: %s", self.turn, actor, action, detail)

    @staticmethod
    def _find_permanent(battlefield: list[Permanent], uid: Optional[str]) -> Optional[Permanent]:
        if not uid:
            return None
        return next((p for p in battlefield if p.uid == uid), None)

    def _remove_dead(self, side: PlayerState) -> None:
        dead = [p for p in side.battlefield if p.is_dead() and p.card.is_creature]
        for p in dead:
            side.battlefield.remove(p)
            side.graveyard.append(p.card)

    def _check_game_over(self) -> bool:
        if self.opponent.life <= 0:
            self.winner = 0
            self.phase = "game_over"
            self._log("system", "game_over", f"You win! Opponent at {self.opponent.life} life on turn {self.turn}")
            return True
        if self.player.life <= 0:
            self.winner = 1
            self.phase = "game_over"
            self._log("system", "game_over", f"You lose. Your life: {self.player.life} on turn {self.turn}")
            return True
        if not self.player.library and not self.player.hand:
            self.winner = 1
            self.phase = "game_over"
            self._log("system", "game_over", "You decked out")
            return True
        return False

    def full_log(self) -> list[dict]:
        return [
            {"turn": e.turn, "actor": e.actor, "action": e.action, "detail": e.detail}
            for e in self.log
        ]


# ---------------------------------------------------------------------------
# Game session store
# ---------------------------------------------------------------------------

_sessions: dict[str, InteractiveGame] = {}


def create_game(player_cards: list["CardInfo"], opponent_cards: list["CardInfo"],
                player_name: str = "Player", opponent_name: str = "Opponent",
                on_the_play: bool = True) -> InteractiveGame:
    """Create and register a new interactive game session."""
    def expand(cards: list["CardInfo"]) -> list["CardInfo"]:
        result = []
        for c in cards:
            if not c.sideboard:
                result.extend([c] * c.quantity)
        return result

    p_lib = expand(player_cards)
    o_lib = expand(opponent_cards)
    random.shuffle(p_lib)
    random.shuffle(o_lib)

    player = PlayerState(name=player_name, library=p_lib)
    opponent = PlayerState(name=opponent_name, library=o_lib)

    # Draw opening hands
    player.draw(7)
    opponent.draw(7)

    # Opponent doesn't mulligan (simplified)
    # Player will decide during mulligan phase

    game_id = str(uuid.uuid4())
    game = InteractiveGame(
        game_id=game_id,
        player=player,
        opponent=opponent,
        turn=1,
        phase="mulligan",
    )
    _sessions[game_id] = game
    return game


def get_game(game_id: str) -> Optional[InteractiveGame]:
    return _sessions.get(game_id)


def remove_game(game_id: str) -> None:
    _sessions.pop(game_id, None)
