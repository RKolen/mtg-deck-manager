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
from deck_registry import CardInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Oracle text helpers
# ---------------------------------------------------------------------------

def _parse_damage(text: str) -> int:
    """Return the first explicit damage number found in oracle text, or 0."""
    m = re.search(r"deals? (\d+) damage", text, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _parse_pump(text: str) -> tuple[int, int]:
    """Return the (power, toughness) bonus from a pump or base-P/T effect."""
    m = re.search(r"gets? \+(\d+)/\+(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"base power and toughness (\d+)/(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def _parse_draw(text: str) -> int:
    """Return the number of cards drawn by a draw effect, or 0 if not found."""
    m = re.search(r"draw (\w+) card", text, re.IGNORECASE)
    if not m:
        return 0
    word = m.group(1).lower()
    word_map = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3}
    return word_map.get(word, int(word) if word.isdigit() else 1)


def _spell_is_affordable(card: CardInfo, available_mana: int) -> bool:
    """True when the player can currently cast this spell.

    Phyrexian mana pips ({W/P}, {G/P}, …) can each be paid with 2 life
    instead of mana, so the minimum mana required is CMC minus the number
    of phyrexian pips.
    """
    if card.is_land:
        return False
    phyrexian_pips = (card.mana_cost or "").upper().count("/P")
    mana_needed = max(0, int(card.cmc) - phyrexian_pips)
    return available_mana >= mana_needed


_CATEGORY_CHECKS: list[tuple[str, str]] = [
    ("burn",    "deals.*damage"),
    ("pump",    r"\+\d/\+\d|gets? \+"),
    ("removal", "destroy|exile"),
    ("draw",    "draw.*card"),
    ("aura",    "enchant "),
]


def _spell_category(card: CardInfo) -> str:
    """Classify a card into a broad effect category for simplified resolution."""
    if card.is_land:
        return "land"
    if card.is_creature:
        return "creature"
    text = (card.oracle_text or "").lower()
    for category, pattern in _CATEGORY_CHECKS:
        if re.search(pattern, text):
            return category
    return "spell"


# ---------------------------------------------------------------------------
# In-play card representation
# ---------------------------------------------------------------------------

@dataclass
class Permanent:
    """A card currently on the battlefield with its combat and counter state."""

    uid: str
    card: CardInfo
    tapped: bool = False
    sick: bool = True
    power_bonus: int = 0
    toughness_bonus: int = 0
    temp_power: int = 0
    temp_toughness: int = 0
    damage: int = 0
    counters: dict[str, int] = field(default_factory=dict)
    attached_to: str | None = None

    @property
    def effective_power(self) -> int:
        """Combat power after all permanent and temporary bonuses."""
        return max(0, self.card.numeric_power + self.power_bonus + self.temp_power
                   + self.counters.get("+1/+1", 0))

    @property
    def effective_toughness(self) -> int:
        """Combat toughness after all permanent and temporary bonuses."""
        return max(1, self.card.numeric_toughness + self.toughness_bonus
                   + self.temp_toughness + self.counters.get("+1/+1", 0))

    def can_attack(self) -> bool:
        """True when this permanent can legally declare as an attacker."""
        has_haste = "haste" in (self.card.oracle_text or "").lower()
        return not self.tapped and (not self.sick or has_haste) and self.card.is_creature

    def is_dead(self) -> bool:
        """True when marked damage equals or exceeds effective toughness."""
        return self.damage >= self.effective_toughness

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict for the frontend."""
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


def _new_permanent(card: CardInfo) -> Permanent:
    """Create a new Permanent for a card entering the battlefield."""
    return Permanent(uid=str(uuid.uuid4())[:8], card=card)


# ---------------------------------------------------------------------------
# Player state
# ---------------------------------------------------------------------------

@dataclass
class PlayerState:
    """All mutable state belonging to one player during a game."""

    name: str
    library: list[CardInfo]
    hand: list[CardInfo] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    graveyard: list[CardInfo] = field(default_factory=list)
    life: int = 20
    mana_spent: int = 0
    land_played: bool = False
    spells_cast_this_turn: int = 0

    def available_mana(self) -> int:
        """Mana remaining after accounting for already-spent mana this turn."""
        lands = sum(1 for p in self.battlefield if p.card.is_land and not p.tapped)
        return max(0, lands - self.mana_spent)

    def total_mana(self) -> int:
        """Total land count (each land produces 1 generic mana)."""
        return sum(1 for p in self.battlefield if p.card.is_land)

    def creatures(self) -> list[Permanent]:
        """All creature permanents currently on the battlefield."""
        return [p for p in self.battlefield if p.card.is_creature]

    def lands(self) -> list[Permanent]:
        """All land permanents currently on the battlefield."""
        return [p for p in self.battlefield if p.card.is_land]

    def draw(self, n: int = 1) -> list[CardInfo]:
        """Draw up to n cards from the top of the library into hand."""
        drawn = self.library[:n]
        self.library = self.library[n:]
        self.hand.extend(drawn)
        return drawn

    def tap_mana(self, amount: int) -> bool:
        """Record mana payment; returns False if insufficient mana available."""
        available = self.total_mana() - self.mana_spent
        if available < amount:
            return False
        self.mana_spent += amount
        return True

    def begin_turn(self) -> None:
        """Untap all permanents and reset per-turn trackers."""
        for p in self.battlefield:
            p.tapped = False
            p.sick = False
            p.temp_power = 0
            p.temp_toughness = 0
            p.damage = 0
        self.mana_spent = 0
        self.land_played = False
        self.spells_cast_this_turn = 0

    def hand_to_dict(self) -> list[dict]:
        """Serialise the hand to a list of JSON-safe card dicts."""
        available = self.total_mana() - self.mana_spent
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
                "affordable": _spell_is_affordable(c, available),
            }
            for i, c in enumerate(self.hand)
        ]


# ---------------------------------------------------------------------------
# Game log entry
# ---------------------------------------------------------------------------

@dataclass
class LogEntry:
    """One line in the game log, attributed to a player or the system."""

    turn: int
    actor: str
    action: str
    detail: str = ""


# ---------------------------------------------------------------------------
# Interactive game
# ---------------------------------------------------------------------------

PHASES = [
    "mulligan", "draw", "main1", "attack", "main2", "end",
    "opp_turn", "declare_blockers", "game_over",
]


@dataclass
class InteractiveGame:
    """Complete state for one interactive game session."""

    game_id: str
    player: PlayerState
    opponent: PlayerState
    turn: int = 1
    phase: str = "mulligan"
    on_the_play: bool = True
    winner: int | None = None
    log: list[LogEntry] = field(default_factory=list)
    pending_attackers: list[str] = field(default_factory=list)
    pending_opp_attackers: list[str] = field(default_factory=list)
    pending_blockers: dict[str, str] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # Serialisation
    # -------------------------------------------------------------------------

    def to_client(self) -> dict:
        """Full game state for the frontend (opponent hand is hidden)."""
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
            "log": [
                {"turn": e.turn, "actor": e.actor, "action": e.action, "detail": e.detail}
                for e in self.log[-20:]
            ],
            "pendingAttackers": self.pending_attackers,
            "opponentAttackers": [
                p.to_dict() for p in self.opponent.battlefield
                if p.uid in self.pending_opp_attackers
            ],
            "pendingBlockers": self.pending_blockers,
            "availableActions": self._available_actions(),
        }

    def _available_actions(self) -> list[str]:
        """Return the set of action names the player may take in the current phase."""
        if self.phase == "mulligan":
            return ["keep", "mulligan"]
        if self.phase in ("game_over", "opp_turn"):
            return []
        if self.phase == "draw":
            return ["auto_draw"]
        if self.phase == "declare_blockers":
            return ["assign_blocker", "unassign_blocker", "confirm_blocks"]
        actions = []
        if self.phase in ("main1", "main2"):
            if not self.player.land_played and any(c.is_land for c in self.player.hand):
                actions.append("play_land")
            available = self.player.total_mana() - self.player.mana_spent
            if any(_spell_is_affordable(c, available) for c in self.player.hand):
                actions.append("cast_spell")
            if self.phase == "main1":
                actions.append("go_to_attack")
            actions.append("end_turn")
        if self.phase == "attack":
            actions.extend(["toggle_attacker", "confirm_attack", "skip_attack"])
        return actions

    # -------------------------------------------------------------------------
    # Player actions
    # -------------------------------------------------------------------------

    def _start_turn_one(self) -> None:
        """Advance past the draw step immediately after the mulligan decision.

        The player already holds their opening hand, so no card is drawn on
        the play. On the draw the opponent goes first, but the player's own
        first draw still happens here before entering main1.
        """
        self.player.begin_turn()
        if self.on_the_play:
            self._log("system", "no_draw", "No draw — on the play, turn 1")
        else:
            drawn = self.player.draw(1)
            name = drawn[0].name if drawn else "—"
            self._log("player", "draw", f"Drew: {name}")
        self.phase = "main1"

    def action_keep(self) -> dict:
        """Keep the current opening hand and begin turn 1."""
        assert self.phase == "mulligan"
        self._log("player", "keep", f"Kept {len(self.player.hand)}-card hand")
        self._start_turn_one()
        return self.to_client()

    def action_mulligan(self) -> dict:
        """Return hand to library, reshuffle, and draw one fewer card."""
        assert self.phase == "mulligan"
        current = len(self.player.hand)
        if current <= 4:
            self._log("player", "keep", f"Forced keep at {current} cards")
            self._start_turn_one()
            return self.to_client()
        self.player.library = self.player.hand + self.player.library
        random.shuffle(self.player.library)
        self.player.hand = []
        self.player.draw(current - 1)
        self._log("player", "mulligan", f"Mulligan to {len(self.player.hand)}")
        return self.to_client()

    def action_draw(self) -> dict:
        """Draw a card at the start of turns 2+."""
        assert self.phase == "draw"
        self.player.begin_turn()
        drawn = self.player.draw(1)
        name = drawn[0].name if drawn else "—"
        self._log("player", "draw", f"Drew: {name}")
        self.phase = "main1"
        return self.to_client()

    def action_play_land(self, hand_idx: int) -> dict:
        """Play a land from hand onto the battlefield."""
        assert self.phase in ("main1", "main2")
        assert not self.player.land_played
        card = self.player.hand.pop(hand_idx)
        assert card.is_land
        self.player.battlefield.append(_new_permanent(card))
        self.player.land_played = True
        self._log("player", "land", card.name)
        return self.to_client()

    def action_cast(
        self,
        hand_idx: int,
        target_uid: str | None = None,
        target_player: int | None = None,
    ) -> dict:
        """Cast a spell from hand; resolves the effect immediately (no stack)."""
        assert self.phase in ("main1", "main2")
        card = self.player.hand[hand_idx]
        assert not card.is_land

        phyrexian_pips = (card.mana_cost or "").upper().count("/P")
        total_cmc = int(card.cmc) if card.cmc == int(card.cmc) else max(1, int(card.cmc))
        mana_needed = max(0, total_cmc - phyrexian_pips)
        life_cost = phyrexian_pips * 2

        if not self.player.tap_mana(mana_needed):
            available = self.player.total_mana() - self.player.mana_spent
            return {
                **self.to_client(),
                "error": f"Not enough mana ({available} available, need {mana_needed})",
            }

        self.player.hand.pop(hand_idx)
        self.player.spells_cast_this_turn += 1
        if life_cost:
            self.player.life -= life_cost
            self._log("player", "phyrexian", f"Paid {life_cost} life for {card.name}")
        self._trigger_prowess()

        category = _spell_category(card)
        detail = self._resolve_spell(card, category, target_uid, target_player)

        self._log("player", "cast", detail)
        self._check_game_over()
        return self.to_client()

    def _trigger_prowess(self) -> None:
        """Grant +1/+1 until end of turn to each prowess creature the player controls."""
        for perm in self.player.creatures():
            if "prowess" in (perm.card.oracle_text or "").lower():
                perm.temp_power += 1
                perm.temp_toughness += 1

    def _resolve_spell(
        self,
        card: CardInfo,
        category: str,
        target_uid: str | None,
        target_player: int | None,
    ) -> str:
        """Dispatch spell resolution by category; return the log detail string."""
        resolvers = {
            "creature": lambda: self._cast_creature(card),
            "burn":     lambda: self._cast_burn(card, target_uid, target_player),
            "pump":     lambda: self._cast_pump(card, target_uid),
            "removal":  lambda: self._cast_removal(card, target_uid),
            "draw":     lambda: self._cast_draw(card),
            "aura":     lambda: self._cast_aura(card, target_uid),
        }
        resolve = resolvers.get(category)
        if resolve:
            return resolve()
        self.player.graveyard.append(card)
        return f"Cast {card.name}"

    def _cast_creature(self, card: CardInfo) -> str:
        """Put a creature onto the battlefield."""
        self.player.battlefield.append(_new_permanent(card))
        return f"Cast creature {card.name} ({card.numeric_power}/{card.numeric_toughness})"

    def _cast_burn(
        self, card: CardInfo, target_uid: str | None, target_player: int | None
    ) -> str:
        """Deal burn damage to a player or creature target."""
        dmg = _parse_damage(card.oracle_text or "") or max(1, int(card.cmc))
        self.player.graveyard.append(card)
        if target_player == 1 or target_uid is None:
            self.opponent.life -= dmg
            return f"{card.name} → {dmg} damage to opponent (life: {self.opponent.life})"
        perm = self._find_permanent(self.opponent.battlefield, target_uid)
        if perm:
            perm.damage += dmg
            self._remove_dead(self.opponent)
            return f"{card.name} → {dmg} damage to {perm.card.name}"
        return f"Cast {card.name} (no valid target)"

    def _cast_pump(self, card: CardInfo, target_uid: str | None) -> str:
        """Apply a power/toughness bonus to a target creature."""
        pp, pt = _parse_pump(card.oracle_text or "")
        if pp == 0 and pt == 0:
            pp, pt = 1, 1
        target = self._find_permanent(self.player.battlefield, target_uid)
        if target is None and self.player.creatures():
            target = self.player.creatures()[-1]
        self.player.graveyard.append(card)
        if not target:
            return f"Cast {card.name} (no target)"
        if "base power and toughness" in (card.oracle_text or "").lower():
            target.temp_power = pp - target.card.numeric_power
            target.temp_toughness = pt - target.card.numeric_toughness
        else:
            target.temp_power += pp
            target.temp_toughness += pt
        self._maybe_trigger_heroic(target, target_uid)
        return f"{card.name} → {target.card.name} gets +{pp}/+{pt} until EOT"

    def _cast_removal(self, card: CardInfo, target_uid: str | None) -> str:
        """Destroy or exile a target permanent."""
        self.player.graveyard.append(card)
        if not target_uid:
            return f"Cast {card.name} (no target)"
        perm = self._find_permanent(self.opponent.battlefield, target_uid)
        if not perm:
            return f"Cast {card.name} (target not found)"
        self.opponent.battlefield.remove(perm)
        self.opponent.graveyard.append(perm.card)
        return f"{card.name} → destroyed {perm.card.name}"

    def _cast_draw(self, card: CardInfo) -> str:
        """Draw cards as specified by the spell's oracle text."""
        n = _parse_draw(card.oracle_text or "") or 1
        drawn = self.player.draw(n)
        self.player.graveyard.append(card)
        return f"{card.name} → drew {', '.join(c.name for c in drawn)}"

    def _cast_aura(self, card: CardInfo, target_uid: str | None) -> str:
        """Attach an aura to a target creature and apply its stat bonuses."""
        perm = _new_permanent(card)
        perm.sick = False
        perm.attached_to = target_uid
        self.player.battlefield.append(perm)
        pp, pt = _parse_pump(card.oracle_text or "")
        if not (pp or pt):
            return f"Enchanted with {card.name}"
        target = self._find_permanent(self.player.battlefield, target_uid)
        if not target:
            return f"Enchanted with {card.name} (no target)"
        target.power_bonus += pp
        target.toughness_bonus += pt
        self._maybe_trigger_heroic(target, target_uid)
        return f"Enchanted {target.card.name} with {card.name}"

    def _maybe_trigger_heroic(self, perm: Permanent, target_uid: str | None) -> None:
        """Fire the heroic trigger if perm has heroic and was the chosen target."""
        if target_uid and "heroic" in (perm.card.oracle_text or "").lower():
            self._resolve_heroic(perm)

    def _resolve_heroic(self, perm: Permanent) -> None:
        """Parse the heroic trigger text and apply the correct effect.

        Heroic oracle text follows the pattern:
          "Heroic — Whenever you cast a spell that targets ~, <effect>."
        The effect is extracted by finding the first comma after "heroic" and
        parsing what follows.
        """
        text = (perm.card.oracle_text or "").lower()
        heroic_idx = text.find("heroic")
        comma_idx = text.find(",", heroic_idx)
        if heroic_idx == -1 or comma_idx == -1:
            return
        effect = text[comma_idx + 1:].strip().rstrip(".")

        if "create" in effect and "token" in effect:
            self._heroic_create_token(effect, perm)
        elif "+1/+1 counter" in effect and "each creature" in effect:
            for p in self.player.creatures():
                p.counters["+1/+1"] = p.counters.get("+1/+1", 0) + 1
            self._log("player", "heroic", f"{perm.card.name}: all creatures +1/+1")
        elif "+1/+1 counter" in effect:
            perm.counters["+1/+1"] = perm.counters.get("+1/+1", 0) + 1
            self._log("player", "heroic", f"{perm.card.name}: +1/+1 counter")
        elif "draw" in effect and "card" in effect:
            n = _parse_draw(effect) or 1
            drawn = self.player.draw(n)
            self._log("player", "heroic", f"{perm.card.name}: drew {len(drawn)} card(s)")
        elif "gain" in effect and "life" in effect:
            m = re.search(r"gain (\d+) life", effect)
            if m:
                amount = int(m.group(1))
                self.player.life += amount
                self._log("player", "heroic", f"{perm.card.name}: gained {amount} life")

    def _heroic_create_token(self, effect: str, source: Permanent) -> None:
        """Create a creature token as directed by a heroic trigger effect text."""
        m = re.search(r"create (?:a|an) (\d+)/(\d+) ([\w ]+?) creature token", effect)
        if not m:
            self._log("player", "heroic", f"{source.card.name}: token (unrecognised text)")
            return
        power, toughness, descriptor = m.group(1), m.group(2), m.group(3).strip()
        color_words = {"white", "blue", "black", "red", "green", "colorless"}
        subtype = " ".join(
            w.title() for w in descriptor.split() if w not in color_words
        )
        token_info = CardInfo(
            name=f"{subtype} Token",
            quantity=1,
            sideboard=False,
            cmc=0,
            type_line=f"Creature — {subtype}",
            pt=f"{power}/{toughness}",
            oracle_text="",
        )
        token_perm = _new_permanent(token_info)
        self.player.battlefield.append(token_perm)
        self._log("player", "heroic", f"{source.card.name}: created {token_info.name}")

    def action_go_to_attack(self) -> dict:
        """Transition from main phase 1 to the declare attackers step."""
        assert self.phase == "main1"
        self.phase = "attack"
        self.pending_attackers = []
        return self.to_client()

    def action_toggle_attacker(self, uid: str) -> dict:
        """Add or remove a creature from the set of declared attackers."""
        assert self.phase == "attack"
        if uid in self.pending_attackers:
            self.pending_attackers.remove(uid)
        else:
            perm = self._find_permanent(self.player.battlefield, uid)
            if perm and perm.can_attack():
                self.pending_attackers.append(uid)
        return self.to_client()

    def action_confirm_attack(self) -> dict:
        """Resolve combat with the declared attackers."""
        assert self.phase == "attack"
        attackers = [p for p in self.player.battlefield if p.uid in self.pending_attackers]
        if attackers:
            damage = self._resolve_combat(attackers, self.opponent)
            names = [a.card.name for a in attackers]
            self._log(
                "player", "attack",
                f"Attacked with {names} → {damage} damage to opponent"
                f" (life: {self.opponent.life})",
            )
        self.pending_attackers = []
        self.phase = "main2"
        self._check_game_over()
        return self.to_client()

    def action_skip_attack(self) -> dict:
        """Pass the combat phase without attacking."""
        assert self.phase == "attack"
        self.pending_attackers = []
        self._log("player", "skip_attack", "Skipped combat")
        self.phase = "main2"
        return self.to_client()

    def action_end_turn(self) -> dict:
        """End the player's turn, run the opponent's main phase, then request blocks."""
        assert self.phase in ("main1", "main2", "attack")
        self._log("player", "end_turn", f"End of turn {self.turn}")
        self.phase = "opp_turn"
        self._opponent_main_phase()
        if self.phase != "game_over":
            self._start_opponent_attack()
        return self.to_client()

    # -------------------------------------------------------------------------
    # Opponent turn — split into main phase and combat so the player can block
    # -------------------------------------------------------------------------

    def _opponent_main_phase(self) -> None:
        """Run the opponent's draw, land drop, and spell-casting steps."""
        opp = self.opponent
        opp.begin_turn()

        drawn = opp.draw(1)
        if drawn:
            self._log("opponent", "draw", f"Drew a card ({len(opp.hand)} in hand)")

        land = next((c for c in opp.hand if c.is_land), None)
        if land and not opp.land_played:
            opp.hand.remove(land)
            opp.battlefield.append(_new_permanent(land))
            opp.land_played = True
            self._log("opponent", "land", land.name)

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
            self._opp_play_card(card, opp)
            if self.phase == "game_over":
                return

    def _start_opponent_attack(self) -> None:
        """Declare the opponent's attackers and hand priority to the player to block."""
        attackers = [p for p in self.opponent.creatures() if p.can_attack()]
        if not attackers:
            self._finish_opponent_turn()
            return
        for perm in attackers:
            perm.tapped = True
        self.pending_opp_attackers = [p.uid for p in attackers]
        names = [p.card.name for p in attackers]
        self._log("opponent", "attack_declared", f"Attacks with {names}")
        self.phase = "declare_blockers"

    def action_assign_blocker(self, blocker_uid: str, attacker_uid: str) -> dict:
        """Assign one of the player's creatures to block an opponent attacker."""
        assert self.phase == "declare_blockers"
        blocker = self._find_permanent(self.player.battlefield, blocker_uid)
        attacker = self._find_permanent(self.opponent.battlefield, attacker_uid)
        if blocker and attacker and not blocker.tapped:
            self.pending_blockers[blocker_uid] = attacker_uid
        return self.to_client()

    def action_unassign_blocker(self, blocker_uid: str) -> dict:
        """Remove a blocking assignment for one of the player's creatures."""
        assert self.phase == "declare_blockers"
        self.pending_blockers.pop(blocker_uid, None)
        return self.to_client()

    def action_confirm_blocks(self) -> dict:
        """Confirm block assignments and resolve the opponent's combat step."""
        assert self.phase == "declare_blockers"
        self._resolve_opponent_combat()
        self._finish_opponent_turn()
        return self.to_client()

    def _resolve_opponent_combat(self) -> None:
        """Resolve the opponent's attack using the player's declared block assignments."""
        attackers = [
            p for p in self.opponent.battlefield if p.uid in self.pending_opp_attackers
        ]
        blockers_for = self._build_blocker_map()
        damage_through = 0
        for atk in attackers:
            has_trample = "trample" in (atk.card.oracle_text or "").lower()
            blockers = blockers_for.get(atk.uid, [])
            damage_through += self._resolve_single_attack(atk, blockers, has_trample)

        self.player.life -= damage_through
        names = [a.card.name for a in attackers]
        self._log(
            "opponent", "attack",
            f"Attacked with {names} → {damage_through} damage (your life: {self.player.life})",
        )

    def _build_blocker_map(self) -> dict[str, list[Permanent]]:
        """Return a mapping of opponent attacker uid → list of assigned player blockers."""
        blockers_for: dict[str, list[Permanent]] = {}
        for blocker_uid, attacker_uid in self.pending_blockers.items():
            blocker = self._find_permanent(self.player.battlefield, blocker_uid)
            if blocker is not None:
                blockers_for.setdefault(attacker_uid, []).append(blocker)
        return blockers_for

    def _resolve_single_attack(
        self, atk: Permanent, blockers: list[Permanent], has_trample: bool
    ) -> int:
        """Resolve one attacker vs. its assigned blockers; return damage to the player.

        All blockers deal their power to the attacker simultaneously.
        The attacker's damage goes to the first blocker (simplified assignment;
        proper multiple-blocker ordering is implemented in Phase E6).
        """
        if not blockers:
            return atk.effective_power
        for blk in blockers:
            atk.damage += blk.effective_power
        blockers[0].damage += atk.effective_power
        self._remove_dead(self.player)
        if atk.is_dead():
            if atk in self.opponent.battlefield:
                self.opponent.battlefield.remove(atk)
                self.opponent.graveyard.append(atk.card)
            return 0
        if has_trample:
            total_toughness = sum(b.effective_toughness for b in blockers)
            return max(0, atk.effective_power - total_toughness)
        return 0

    def _finish_opponent_turn(self) -> None:
        """Clean up combat state and advance to the player's next turn."""
        self.pending_opp_attackers = []
        self.pending_blockers = {}
        if not self._check_game_over():
            self.turn += 1
            self.phase = "draw"

    def _opp_play_card(self, card: CardInfo, opp: PlayerState) -> None:
        """Resolve one spell cast by the AI opponent."""
        category = _spell_category(card)
        if category == "creature":
            opp.battlefield.append(_new_permanent(card))
            self._log(
                "opponent", "cast",
                f"{card.name} ({card.numeric_power}/{card.numeric_toughness})",
            )
        elif category == "burn":
            dmg = _parse_damage(card.oracle_text or "") or max(1, int(card.cmc))
            self.player.life -= dmg
            opp.graveyard.append(card)
            self._log(
                "opponent", "burn",
                f"{card.name} → {dmg} damage to you (your life: {self.player.life})",
            )
        elif category == "removal":
            targets = sorted(self.player.creatures(), key=lambda p: -p.effective_power)
            if targets:
                victim = targets[0]
                self.player.battlefield.remove(victim)
                self.player.graveyard.append(victim.card)
                self._log("opponent", "removal", f"{card.name} → destroyed your {victim.card.name}")
            opp.graveyard.append(card)
        elif category == "pump":
            targets = sorted(opp.creatures(), key=lambda p: -p.effective_power)
            if targets:
                pp, pt = _parse_pump(card.oracle_text or "")
                targets[0].power_bonus += pp
                targets[0].toughness_bonus += pt
            opp.graveyard.append(card)
            self._log("opponent", "cast", card.name)
        else:
            opp.graveyard.append(card)
            self._log("opponent", "cast", card.name)
        self._check_game_over()

    # -------------------------------------------------------------------------
    # Combat resolution
    # -------------------------------------------------------------------------

    def _resolve_combat(
        self,
        attackers: list[Permanent],
        defender_state: PlayerState,
        defender_side: PlayerState | None = None,
    ) -> int:
        """Resolve combat: optimal blocking, damage assignment, death checks.

        Returns the total unblocked damage dealt to the defending player.
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
            has_trample = "trample" in (atk.card.oracle_text or "").lower()
            if blockers:
                blk = blockers.pop(0)
                damage_through += self._apply_block(atk, blk, defender_side, has_trample)
            else:
                damage_through += atk.effective_power

        defender_state.life -= damage_through
        return damage_through

    def _apply_block(
        self,
        atk: Permanent,
        blk: Permanent,
        defender_side: PlayerState,
        has_trample: bool,
    ) -> int:
        """Apply damage between one attacker and one blocker; return trample damage."""
        atk.damage += blk.effective_power
        blk.damage += atk.effective_power
        trample_damage = 0
        if blk.is_dead():
            if blk in defender_side.battlefield:
                defender_side.battlefield.remove(blk)
                defender_side.graveyard.append(blk.card)
            if has_trample:
                excess = atk.effective_power - blk.effective_toughness
                trample_damage = max(0, excess)
        if atk.is_dead():
            if atk in self.player.battlefield:
                self.player.battlefield.remove(atk)
                self.player.graveyard.append(atk.card)
            elif atk in self.opponent.battlefield:
                self.opponent.battlefield.remove(atk)
                self.opponent.graveyard.append(atk.card)
        return trample_damage

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _log(self, actor: str, action: str, detail: str = "") -> None:
        """Append an entry to the game log."""
        self.log.append(LogEntry(turn=self.turn, actor=actor, action=action, detail=detail))
        logger.debug("T%d [%s] %s: %s", self.turn, actor, action, detail)

    @staticmethod
    def _find_permanent(battlefield: list[Permanent], uid: str | None) -> Permanent | None:
        """Return the permanent with the given uid from a battlefield list."""
        if not uid:
            return None
        return next((p for p in battlefield if p.uid == uid), None)

    def _remove_dead(self, side: PlayerState) -> None:
        """Move creatures with lethal damage to the graveyard, cascading to auras."""
        dead = [p for p in side.battlefield if p.is_dead() and p.card.is_creature]
        for perm in dead:
            side.battlefield.remove(perm)
            side.graveyard.append(perm.card)
            auras = [a for a in side.battlefield if a.attached_to == perm.uid]
            for aura in auras:
                side.battlefield.remove(aura)
                side.graveyard.append(aura.card)

    def _check_game_over(self) -> bool:
        """Set game_over phase and winner if a win condition is met."""
        if self.opponent.life <= 0:
            self.winner = 0
            self.phase = "game_over"
            self._log(
                "system", "game_over",
                f"You win! Opponent at {self.opponent.life} life on turn {self.turn}",
            )
            return True
        if self.player.life <= 0:
            self.winner = 1
            self.phase = "game_over"
            self._log(
                "system", "game_over",
                f"You lose. Your life: {self.player.life} on turn {self.turn}",
            )
            return True
        if not self.player.library and not self.player.hand:
            self.winner = 1
            self.phase = "game_over"
            self._log("system", "game_over", "You decked out")
            return True
        return False

    def full_log(self) -> list[dict]:
        """Return the complete game log as a list of JSON-safe dicts."""
        return [
            {"turn": e.turn, "actor": e.actor, "action": e.action, "detail": e.detail}
            for e in self.log
        ]


# ---------------------------------------------------------------------------
# Game session store
# ---------------------------------------------------------------------------

_sessions: dict[str, InteractiveGame] = {}


def _expand_deck(cards: list[CardInfo]) -> list[CardInfo]:
    """Expand a deck list by quantity into individual card instances."""
    result = []
    for card in cards:
        if not card.sideboard:
            result.extend([card] * card.quantity)
    return result


def create_game(
    player_cards: list[CardInfo],
    opponent_cards: list[CardInfo],
    player_name: str = "Player",
    opponent_name: str = "Opponent",
    on_the_play: bool = True,
) -> InteractiveGame:
    """Create and register a new interactive game session."""
    p_lib = _expand_deck(player_cards)
    o_lib = _expand_deck(opponent_cards)
    random.shuffle(p_lib)
    random.shuffle(o_lib)

    player = PlayerState(name=player_name, library=p_lib)
    opponent = PlayerState(name=opponent_name, library=o_lib)
    player.draw(7)
    opponent.draw(7)

    game_id = str(uuid.uuid4())
    game = InteractiveGame(
        game_id=game_id,
        player=player,
        opponent=opponent,
        turn=1,
        phase="mulligan",
        on_the_play=on_the_play,
    )
    _sessions[game_id] = game
    return game


def get_game(game_id: str) -> InteractiveGame | None:
    """Retrieve an active game session by ID."""
    return _sessions.get(game_id)


def remove_game(game_id: str) -> None:
    """Remove a game session from the store."""
    _sessions.pop(game_id, None)
