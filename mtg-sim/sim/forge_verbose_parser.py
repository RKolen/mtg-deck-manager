"""Parse Forge verbose simulation stdout into SimResult objects."""

from __future__ import annotations

import random
import re
from typing import Optional

from _sim_types import (
    GameLog,
    GameLogLife,
    GameLogMulligans,
    GameLogOutcome,
    GameLogSetup,
    PilotNotesGroup,
    SimResult,
    SimResultLife,
    SimResultMulligans,
    SimResultOutcome,
    TurnBoard,
    TurnDamage,
    TurnEvent,
    _GameState,
    _TurnAccum,
)

class _ForgeVerboseParser:
    """Line-by-line parser for Forge verbose (no -q flag) stdout."""

    _MULLIGAN = re.compile(r"Mulligan: (.+?) has kept a hand of (\d+) cards")
    _TURN_START = re.compile(r"Turn: Turn (\d+) \((.+)\)")
    _LIFE = re.compile(r"Life: Life: (.+?) \d+ > (\d+)")
    _CAST = re.compile(r"Add To Stack: (.+?) cast (.+)")
    _LAND = re.compile(r"Land: (.+?) played (.+)")
    # Groups: (source, amount, damage_type_or_None, target)
    _DAMAGE = re.compile(
        r"Damage: (.+?) deals (\d+)(?: (combat|non-combat))? damage(?:.*?)? to (.+?)\.",
        re.IGNORECASE,
    )
    _TURN_OUTCOME = re.compile(r"Game Outcome: Turn (\d+)", re.IGNORECASE)
    _GAME_RESULT = re.compile(
        r"Game Result: Game (\d+) ended.*?(?:(\S.*?) has won!|a Draw)",
        re.IGNORECASE,
    )
    _PILOT_TAGGED = re.compile(r"^\[Pilot\] (Ai\(\d+\)-[^:]+): (.+)$")
    _PILOT_LEGACY_ACTIVE = re.compile(r"^\[Pilot\] (Ai\(\d+\)-[^:]+): active$")
    _PILOT_UNTAGGED_ACTIVE = re.compile(r"^\[Pilot\] active$")
    _PILOT_MULLIGAN_CHOICE = re.compile(r"^mulligan: (Keep|Mulligan)\b", re.I)
    _PILOT_SPELL = re.compile(
        r"^(?:\[Pilot\] (?:Ai\(\d+\)-[^:]+): )?T(\d+) spell: (.+?)(?: — (.+))?$"
    )
    _PILOT_ATTACK = re.compile(
        r"T(\d+) attack: Attack with all \((\d+) creatures?\)", re.I
    )
    _PILOT_HAND = re.compile(r"\[hand:(\d+)\]")
    _PILOT_HAND_CARDS = re.compile(r"\[cards:([^\]]+)\]")
    _PILOT_TURN = re.compile(r"T(\d+)")

    def _board_creature_count(self, turn: int, side: int) -> int:
        """Creatures on board at end of a turn (from pilot attack lines for that turn)."""
        exact = self._st.extras.attack_by_turn.get((turn, side))
        if exact is not None:
            return exact
        best_turn = -1
        best_count = 0
        for (prior_turn, prior_side), count in self._st.extras.attack_by_turn.items():
            if prior_side == side and best_turn <= prior_turn < turn:
                best_turn = prior_turn
                best_count = count
        return best_count

    def _hand_size_for_turn(self, turn: int, side: int) -> int:
        """Cards in hand during a turn (from pilot [hand:N] tags on that turn)."""
        exact = self._st.extras.hand_by_turn.get((turn, side))
        if exact is not None:
            return exact
        best_turn = -1
        best_size = 0
        for (prior_turn, prior_side), size in self._st.extras.hand_by_turn.items():
            if prior_side == side and best_turn <= prior_turn < turn:
                best_turn = prior_turn
                best_size = size
        return best_size

    def _hand_cards_for_turn(self, turn: int, side: int) -> str:
        """Last known hand contents for a turn (from pilot [cards:...] tags)."""
        exact = self._st.extras.hand_cards_by_turn.get((turn, side))
        if exact:
            return exact
        best_turn = -1
        best_cards = ""
        for (prior_turn, prior_side), cards in self._st.extras.hand_cards_by_turn.items():
            if prior_side == side and best_turn <= prior_turn < turn and cards:
                best_turn = prior_turn
                best_cards = cards
        return best_cards

    def _record_pilot_hand(self, side: int | None, detail: str) -> None:
        """Store hand size and card list from pilot tags."""
        if side is None:
            return
        hand_match = self._PILOT_HAND.search(detail)
        cards_match = self._PILOT_HAND_CARDS.search(detail)
        turn_match = self._PILOT_TURN.search(detail)
        if not turn_match:
            return
        turn = int(turn_match.group(1))
        if hand_match:
            self._st.extras.hand_by_turn[(turn, side)] = int(hand_match.group(1))
        if cards_match:
            self._st.extras.hand_cards_by_turn[(turn, side)] = cards_match.group(1).strip()

    def __init__(self, player_name: str) -> None:
        """Initialise parser with the short player deck name."""
        self._player_name = player_name
        self._p_forge = f"Ai(1)-{player_name}"
        self._results: list[SimResult] = []
        self._st = _GameState()
        self._mull_pending = [0, 0]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _flush(self) -> None:
        """Commit the current half-turn data to turn_events."""
        if self._st.meta.half_player < 0:
            return
        mana = self._st.accum.p_lands if self._st.meta.half_player == 0 else 0
        side = self._st.meta.half_player
        turn = self._st.meta.game_turn
        creatures = self._board_creature_count(turn, side)
        board_power = max(creatures, self._st.accum.combat_dmg)
        hand_size = self._hand_size_for_turn(turn, side)
        hand_cards = self._hand_cards_for_turn(turn, side)
        self._st.turn_events.append(TurnEvent(
            turn=self._st.meta.game_turn,
            player=self._st.meta.half_player,
            mana_available=mana,
            plays=list(self._st.accum.plays),
            life_totals=[self._st.life.p, self._st.life.o],
            board=TurnBoard(
                hand_size=hand_size,
                hand_cards=hand_cards,
                creatures_in_play=creatures,
                power=board_power,
            ),
            damage=TurnDamage(
                total=self._st.accum.dmg,
                combat=self._st.accum.combat_dmg,
                noncombat=self._st.accum.noncombat_dmg,
            ),
        ))

    def _commit(self, game_num: int, winner_raw: Optional[str]) -> None:
        """Finalise a game and append a SimResult."""
        on_play = game_num % 2 == 1
        if winner_raw is None:
            winner = random.randint(0, 1)
            if not self._st.win_cond:
                self._st.win_cond = "draw"
        else:
            winner = 0 if self._player_name in winner_raw else 1
        key_cards = (
            [c for c, _ in self._st.extras.opp_dmg.most_common(5)] if winner == 1 else []
        )
        final_turn = self._st.meta.turn_num or self._st.meta.game_turn
        log = GameLog(
            setup=GameLogSetup(game_index=game_num - 1, on_the_play=on_play),
            mulligans=GameLogMulligans(
                player=self._st.mulls[0],
                opponent=self._st.mulls[1],
            ),
            player_opening_hand=[],
            turns=list(self._st.turn_events),
            outcome=GameLogOutcome(
                winner=winner,
                final_turn=final_turn,
                win_condition=self._st.win_cond,
            ),
            life=GameLogLife(
                player=self._st.life.p,
                opponent=self._st.life.o,
            ),
            pilots=PilotNotesGroup(
                all_notes=list(self._st.extras.pilot_notes),
                player=list(self._st.extras.player_pilot_notes),
                opponent=list(self._st.extras.opponent_pilot_notes),
            ),
        )
        self._results.append(SimResult(
            outcome=SimResultOutcome(winner=winner, timed_out=winner_raw is None),
            turns=self._st.meta.turn_num,
            life=SimResultLife(player=self._st.life.p, opponent=self._st.life.o),
            key_cards_on_loss=key_cards,
            on_the_play=on_play,
            mulligans=SimResultMulligans(
                player=self._st.mulls[0],
                opponent=self._st.mulls[1],
            ),
            log=log,
        ))
        self._st = _GameState()
        self._mull_pending = [0, 0]

    # ------------------------------------------------------------------
    # Per-prefix handlers (return True when the line was consumed)
    # ------------------------------------------------------------------

    def _try_mulligan(self, s: str) -> bool:
        """Handle Forge Mulligan log lines (informational only).

        London mulligan always keeps seven cards, so hand size does not encode
        how many times a player mulliganed. Counts come from [Pilot] lines.
        """
        return bool(self._MULLIGAN.match(s))

    def _record_pilot_mulligan(self, side: int | None, detail: str) -> None:
        """Update mulligan counts from a pilot keep/mulligan decision."""
        if side is None:
            return
        match = self._PILOT_MULLIGAN_CHOICE.match(detail.strip())
        if not match:
            return
        choice = match.group(1).lower()
        if choice == "mulligan":
            self._mull_pending[side] += 1
        elif choice == "keep":
            self._st.mulls[side] = self._mull_pending[side]
            self._mull_pending[side] = 0

    def _try_turn_start(self, s: str) -> bool:
        """Handle Turn start lines."""
        m = self._TURN_START.match(s)
        if not m:
            return False
        self._flush()
        self._st.meta.game_turn = int(m.group(1))
        self._st.meta.half_player = 0 if self._p_forge in m.group(2) else 1
        self._st.accum = _TurnAccum()
        return True

    def _try_life(self, s: str) -> bool:
        """Handle Life change lines."""
        m = self._LIFE.match(s)
        if not m:
            return False
        new_life = int(m.group(2))
        if self._p_forge in m.group(1):
            self._st.life.p = new_life
        else:
            self._st.life.o = new_life
        return True

    def _try_cast(self, s: str) -> bool:
        """Handle Add To Stack cast lines."""
        m = self._CAST.match(s)
        if not m:
            return False
        is_player = self._p_forge in m.group(1)
        card = re.sub(r"\s+targeting .+$", "", m.group(2)).strip()
        if is_player == (self._st.meta.half_player == 0):
            self._st.accum.plays.append(card)
        return True

    def _try_land(self, s: str) -> bool:
        """Handle Land played lines."""
        m = self._LAND.match(s)
        if not m:
            return False
        is_player = self._p_forge in m.group(1)
        land = re.sub(r"\s*\(\d+\)\s*$", "", m.group(2)).strip()
        if is_player:
            self._st.accum.p_lands += 1
        if is_player == (self._st.meta.half_player == 0):
            self._st.accum.plays.append(f"{land} [Land]")
        return True

    def _try_damage(self, s: str) -> bool:
        """Handle Damage lines."""
        m = self._DAMAGE.match(s)
        if not m:
            return False
        source_raw = m.group(1)
        amount = int(m.group(2))
        dmg_type = (m.group(3) or "").lower()
        target = m.group(4)
        target_is_player = self._p_forge in target
        # Track which opponent cards damage the player (for key_cards_on_loss).
        if target_is_player:
            card_name = re.sub(r"\s*\(\d+\)\s*$", "", source_raw).strip()
            self._st.extras.opp_dmg[card_name] += amount
        # Per-turn damage is what the active player deals to the defending
        # player, regardless of which side is active. Self-damage (fetch lands,
        # Phyrexian mana) is excluded because active and target are the same side.
        active_is_player = self._st.meta.half_player == 0
        if self._st.meta.half_player >= 0 and active_is_player != target_is_player:
            self._st.accum.dmg += amount
            if dmg_type == "combat":
                self._st.accum.combat_dmg += amount
            elif dmg_type == "non-combat":
                self._st.accum.noncombat_dmg += amount
        return True

    def _try_turn_outcome(self, s: str) -> bool:
        """Handle Game Outcome turn lines."""
        m = self._TURN_OUTCOME.match(s)
        if not m:
            return False
        self._st.meta.turn_num = int(m.group(1))
        return True

    def _try_win_cond(self, s: str) -> bool:
        """Handle Game Outcome player-outcome lines, extracting the real loss reason.

        Forge emits one line per player, e.g.:
          Game Outcome: Ai(1)-Deck has won because all opponents have lost
          Game Outcome: Ai(2)-Opp has lost because life total reached 0
        The loser's line carries the diagnostic reason; the winner's generic
        line does not override a more specific reason already recorded.
        """
        if not s.startswith("Game Outcome:"):
            return False
        lower = s.lower()
        if "life total reached 0" in lower:
            self._st.win_cond = "life_loss"
        elif "draw cards from empty library" in lower:
            self._st.win_cond = "deck_out"
        elif "10 poison counters" in lower:
            self._st.win_cond = "poisoned"
        elif "has conceded" in lower:
            self._st.win_cond = "concession"
        elif "effect of spell" in lower or "won by spell" in lower:
            self._st.win_cond = "lose_the_game_effect"
        elif "21 damage from generals" in lower:
            self._st.win_cond = "commander_damage"
        elif "accepted that the game is a draw" in lower:
            self._st.win_cond = "draw"
        elif "has won due to effect of" in lower:
            self._st.win_cond = "lose_the_game_effect"
        # "has won because all opponents have lost" — generic; do not overwrite
        # a specific reason already set from the loser's line.
        return True

    def _pilot_side(self, tag: str) -> int | None:
        """Map Forge Ai(N) label to sim player index (0=player deck, 1=opponent)."""
        if tag.startswith("Ai(1)"):
            return 0
        if tag.startswith("Ai(2)"):
            return 1
        return None

    def _record_pilot_note(self, side: int | None, line: str) -> None:
        """Store a pilot log line, split by deck when side is known."""
        self._st.extras.pilot_notes.append(line)
        if side == 0:
            self._st.extras.player_pilot_notes.append(line)
        elif side == 1:
            self._st.extras.opponent_pilot_notes.append(line)

    def _try_pilot(self, s: str) -> bool:
        """Handle standardized [Pilot] lines from Forge LLM pilot integration."""
        if not s.startswith("[Pilot]"):
            return False

        tagged = self._PILOT_TAGGED.match(s)
        if tagged:
            side = self._pilot_side(tagged.group(1))
            detail = tagged.group(2)
            self._record_pilot_mulligan(side, detail)
            self._record_pilot_hand(side, detail)
            attack = self._PILOT_ATTACK.search(detail)
            if attack and side is not None:
                turn = int(attack.group(1))
                count = int(attack.group(2))
                self._st.extras.attack_by_turn[(turn, side)] = count
            display = f"[Pilot] {tagged.group(1)}: {detail}"
            self._record_pilot_note(side, display)
            spell = self._PILOT_SPELL.match(detail)
            if spell and self._st.meta.half_player >= 0:
                turn_num = spell.group(1)
                card = re.sub(r"\s*\[hand:\d+\]", "", spell.group(2)).strip()
                reason = spell.group(3) or ""
                play = f"{card} [Pilot T{turn_num}]"
                if reason:
                    play += f" — {reason}"
                self._st.accum.plays.append(play)
            return True

        legacy_active = self._PILOT_LEGACY_ACTIVE.match(s)
        if legacy_active:
            side = self._pilot_side(legacy_active.group(1))
            self._record_pilot_note(side, s)
            return True

        if self._PILOT_UNTAGGED_ACTIVE.match(s):
            self._record_pilot_note(None, s)
            return True

        self._record_pilot_note(None, s)
        spell = self._PILOT_SPELL.match(s.removeprefix("[Pilot] ").strip())
        if not spell:
            spell = self._PILOT_SPELL.match(s)
        if spell and self._st.meta.half_player >= 0:
            turn_num = spell.group(1)
            card = re.sub(r"\s*\[hand:\d+\]", "", spell.group(2)).strip()
            reason = spell.group(3) or ""
            play = f"{card} [Pilot T{turn_num}]"
            if reason:
                play += f" — {reason}"
            self._st.accum.plays.append(play)
        return True

    def _try_game_result(self, s: str) -> bool:
        """Handle Game Result lines (end of game)."""
        m = self._GAME_RESULT.search(s)
        if not m:
            return False
        self._flush()
        self._commit(int(m.group(1)), m.group(2))
        return True

    def feed(self, line: str) -> None:
        """Process one line of Forge verbose output."""
        s = line.strip()
        for handler in (
            self._try_pilot,
            self._try_mulligan,
            self._try_turn_start,
            self._try_life,
            self._try_cast,
            self._try_land,
            self._try_damage,
            self._try_turn_outcome,
            self._try_win_cond,
            self._try_game_result,
        ):
            if handler(s):
                break

    def results(self) -> list[SimResult]:
        """Return all completed SimResult objects."""
        return list(self._results)


def _parse_forge_verbose_output(stdout: str, player_name: str) -> list[SimResult]:
    """Parse Forge verbose stdout (no -q flag) into rich SimResult objects."""
    parser = _ForgeVerboseParser(player_name)
    for line in stdout.splitlines():
        parser.feed(line)
    return parser.results()
