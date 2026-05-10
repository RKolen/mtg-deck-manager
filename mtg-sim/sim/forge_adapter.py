"""
ForgeAdapter — manages the Forge headless subprocess and socket protocol.

When FORGE_JAR, FORGE_HOST, and FORGE_PORT are all set the adapter launches
Forge and routes decisions through the socket. Otherwise it runs in mock mode,
simulating games from actual deck composition (CMC, card types, power/toughness).

The mock engine models:
  - Opening hand drawing and mulligan decisions (2–5 lands to keep)
  - Turn-by-turn land drops and spell casting (cheapest spells first)
  - Combat: all creatures attack, opponent blocks to minimise damage
  - Life-total tracking through the game
  - Creature summoning sickness (don't attack turn they enter)
"""

from __future__ import annotations

import json
import logging
import os
import random
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Protocol, cast

if TYPE_CHECKING:
    from deck_registry import CardInfo

logger = logging.getLogger(__name__)


class _SocketFile(Protocol):
    def write(self, buffer: bytes, /) -> int: ...
    def flush(self) -> None: ...
    def readline(self) -> bytes: ...
    def close(self) -> None: ...


FORGE_JAR: str = os.environ.get("FORGE_JAR", "")
FORGE_HOST: str = os.environ.get("FORGE_HOST", "")
FORGE_PORT: str = os.environ.get("FORGE_PORT", "")


def _forge_available() -> bool:
    return bool(FORGE_JAR and FORGE_HOST and FORGE_PORT and os.path.isfile(FORGE_JAR))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TurnEvent:
    """One player's full turn within a game."""
    turn: int
    player: int                  # 0 = simulated player, 1 = opponent
    mana_available: int
    plays: list[str]             # e.g. ["[Land] Stomping Ground", "[Creature] Ragavan"]
    damage_dealt: int            # damage pushed through to the opponent this turn
    life_totals: list[int]       # [player_life, opp_life] after this turn
    hand_size: int
    creatures_in_play: int       # count of own creatures after this turn
    board_power: int             # total attack power on board (own side)


@dataclass
class GameLog:
    """Complete record of a single simulated game."""
    game_index: int
    on_the_play: bool
    player_mulligan: int
    opponent_mulligan: int
    player_opening_hand: list[str]   # card names
    turns: list[TurnEvent]
    winner: int                      # 0 = player, 1 = opponent
    final_turn: int
    player_final_life: int
    opponent_final_life: int
    win_condition: str               # "aggro beatdown" | "control" | "combo" | "time"


@dataclass
class SimResult:
    """Outcome of a single simulated game — passed to sim_statistics."""
    winner: int
    turns: int
    player_life: int
    opponent_life: int
    key_cards_on_loss: list[str] = field(default_factory=list)
    on_the_play: bool = True
    player_mulligan: int = 0
    opponent_mulligan: int = 0
    log: Optional[GameLog] = None

    @property
    def player_won(self) -> bool:
        return self.winner == 0


# ---------------------------------------------------------------------------
# Mock game engine
# ---------------------------------------------------------------------------

class _BoardSide:
    """Tracks one player's in-game state."""

    def __init__(self, cards: list["CardInfo"]) -> None:
        self.library: list["CardInfo"] = cards.copy()
        random.shuffle(self.library)
        self.hand: list["CardInfo"] = []
        self.lands: list["CardInfo"] = []
        self.creatures: list["CardInfo"] = []
        # Summoning sickness: creatures added this turn can't attack
        self.fresh_creatures: list["CardInfo"] = []
        self.graveyard: list["CardInfo"] = []
        self.life: int = 20
        self.mulligan_count: int = 0

    # --- Opening hand --------------------------------------------------

    def draw_opening_hand(self) -> None:
        """Draw 7 and mulligan until hand quality is acceptable (≤3 attempts)."""
        for attempt in range(4):
            hand_size = 7 - attempt
            random.shuffle(self.library)
            hand = self.library[:hand_size]
            land_count = sum(1 for c in hand if c.is_land)
            # Keep if 2..5 lands (loosen for small hands)
            lo = 2 if hand_size >= 6 else 1
            hi = min(hand_size - 1, 5)
            if lo <= land_count <= hi or attempt == 3:
                self.hand = list(hand)
                self.library = self.library[hand_size:]
                self.mulligan_count = attempt
                return

    def draw(self) -> None:
        if self.library:
            self.hand.append(self.library.pop(0))

    # --- Turn actions --------------------------------------------------

    def clear_sickness(self) -> None:
        self.fresh_creatures.clear()

    def play_land(self) -> Optional["CardInfo"]:
        """Play one land from hand if available."""
        for c in self.hand:
            if c.is_land:
                self.hand.remove(c)
                self.lands.append(c)
                return c
        return None

    def cast_spells(self, turn: int) -> list["CardInfo"]:
        """Cast as many affordable non-land spells as possible (cheapest first)."""
        mana = len(self.lands)
        spent = 0
        cast: list["CardInfo"] = []
        # Sort by CMC so we maximise card count, then CMC descending for value
        affordable = sorted(
            [c for c in self.hand if not c.is_land and c.cmc <= mana - spent],
            key=lambda c: c.cmc,
        )
        for card in affordable:
            if spent + card.cmc <= mana:
                spent += int(card.cmc) if card.cmc == int(card.cmc) else 1
                self.hand.remove(card)
                cast.append(card)
                if card.is_creature:
                    self.creatures.append(card)
                    self.fresh_creatures.append(card)
        return cast

    def attack_power(self) -> int:
        """Return total power of untapped (non-sick) creatures."""
        eligible = [c for c in self.creatures if c not in self.fresh_creatures]
        return sum(c.numeric_power for c in eligible)

    def attackers(self) -> list["CardInfo"]:
        return [c for c in self.creatures if c not in self.fresh_creatures]

    def take_damage(self, damage: int) -> None:
        self.life = max(0, self.life - damage)

    def total_toughness(self) -> int:
        return sum(c.numeric_toughness for c in self.creatures)


def _resolve_combat(attacker_side: _BoardSide, defender_side: _BoardSide) -> int:
    """
    Simplified combat: all eligible creatures attack, defender blocks to absorb
    as much damage as possible (blocks strongest creatures first).
    Returns damage dealt to the defending player.
    """
    attackers = attacker_side.attackers()
    if not attackers:
        return 0

    defenders = sorted(defender_side.creatures, key=lambda c: c.numeric_toughness, reverse=True)
    sorted_attackers = sorted(attackers, key=lambda c: c.numeric_power, reverse=True)

    remaining_block = sum(c.numeric_toughness for c in defenders)
    damage_through = 0

    for atk in sorted_attackers:
        if remaining_block >= atk.numeric_power:
            remaining_block -= atk.numeric_power  # fully blocked
        else:
            damage_through += atk.numeric_power - max(0, remaining_block)
            remaining_block = 0

    return max(0, damage_through)


class MockGameEngine:
    """
    Simulates MTG games from actual deck card data without the Forge rules engine.

    The simulation models:
    - Realistic opening-hand mulligan decisions
    - Turn-by-turn land drops and spell casting
    - Simplified combat damage (all-in attacks, optimal blocking)
    - Creatures having summoning sickness the turn they enter
    """

    MAX_TURNS = 12

    def run(
        self,
        player_cards: list["CardInfo"],
        opponent_cards: list["CardInfo"],
        on_the_play: bool,
        game_index: int = 0,
    ) -> SimResult:
        # Expand quantities into individual card instances
        p_lib = self._expand(player_cards)
        o_lib = self._expand(opponent_cards)

        player = _BoardSide(p_lib)
        opponent = _BoardSide(o_lib)

        player.draw_opening_hand()
        opponent.draw_opening_hand()

        player_opening_hand = [c.name for c in player.hand]
        turn_events: list[TurnEvent] = []

        winner = 1  # default: opponent wins if time runs out with lower life
        final_turn = self.MAX_TURNS
        win_condition = "time"

        for turn in range(1, self.MAX_TURNS + 1):
            # Resolve summoning sickness from previous turn
            player.clear_sickness()
            opponent.clear_sickness()

            # --- Player's turn ---
            player.draw()
            land = player.play_land()
            cast = player.cast_spells(turn)

            plays: list[str] = []
            if land:
                plays.append(f"[Land] {land.name}")
            for c in cast:
                plays.append(f"[{c.short_type()}] {c.name}")

            # Combat (player attacks opponent)
            dmg_to_opp = _resolve_combat(player, opponent)
            opponent.take_damage(dmg_to_opp)

            turn_events.append(TurnEvent(
                turn=turn,
                player=0,
                mana_available=len(player.lands),
                plays=plays,
                damage_dealt=dmg_to_opp,
                life_totals=[player.life, opponent.life],
                hand_size=len(player.hand),
                creatures_in_play=len(player.creatures),
                board_power=player.attack_power(),
            ))

            if opponent.life <= 0:
                winner = 0
                final_turn = turn
                win_condition = self._classify_win(player_cards)
                break

            # --- Opponent's turn ---
            opponent.draw()
            land = opponent.play_land()
            o_cast = opponent.cast_spells(turn)

            o_plays: list[str] = []
            if land:
                o_plays.append(f"[Land] {land.name}")
            for c in o_cast:
                o_plays.append(f"[{c.short_type()}] {c.name}")

            dmg_to_player = _resolve_combat(opponent, player)
            player.take_damage(dmg_to_player)

            turn_events.append(TurnEvent(
                turn=turn,
                player=1,
                mana_available=len(opponent.lands),
                plays=o_plays,
                damage_dealt=dmg_to_player,
                life_totals=[player.life, opponent.life],
                hand_size=len(opponent.hand),
                creatures_in_play=len(opponent.creatures),
                board_power=opponent.attack_power(),
            ))

            if player.life <= 0:
                winner = 1
                final_turn = turn
                win_condition = self._classify_win(opponent_cards)
                break
        else:
            # Game went to time
            winner = 0 if player.life > opponent.life else 1
            win_condition = "time"

        # Cards on the board when opponent won (top threats)
        key_cards: list[str] = []
        if winner == 1:
            key_cards = random.sample(
                [c.name for c in opponent.creatures],
                k=min(3, len(opponent.creatures)),
            ) if opponent.creatures else []

        log = GameLog(
            game_index=game_index,
            on_the_play=on_the_play,
            player_mulligan=player.mulligan_count,
            opponent_mulligan=opponent.mulligan_count,
            player_opening_hand=player_opening_hand,
            turns=turn_events,
            winner=winner,
            final_turn=final_turn,
            player_final_life=player.life,
            opponent_final_life=opponent.life,
            win_condition=win_condition,
        )

        return SimResult(
            winner=winner,
            turns=final_turn,
            player_life=player.life,
            opponent_life=opponent.life,
            key_cards_on_loss=key_cards,
            on_the_play=on_the_play,
            player_mulligan=player.mulligan_count,
            opponent_mulligan=opponent.mulligan_count,
            log=log,
        )

    @staticmethod
    def _expand(cards: list["CardInfo"]) -> list["CardInfo"]:
        result: list["CardInfo"] = []
        for c in cards:
            if not c.sideboard:
                result.extend([c] * c.quantity)
        return result

    @staticmethod
    def _classify_win(winning_deck: list["CardInfo"]) -> str:
        """Guess win condition from deck composition."""
        non_sb = [c for c in winning_deck if not c.sideboard]
        if not non_sb:
            return "unknown"
        total = sum(c.quantity for c in non_sb)
        creature_qty = sum(c.quantity for c in non_sb if c.is_creature)
        avg_cmc = (
            sum(c.cmc * c.quantity for c in non_sb if not c.is_land) /
            max(1, sum(c.quantity for c in non_sb if not c.is_land))
        )
        if avg_cmc < 2.0 and creature_qty / max(1, total) > 0.35:
            return "aggro beatdown"
        if avg_cmc > 3.5:
            return "midrange / control"
        return "tempo / midrange"


# ---------------------------------------------------------------------------
# ForgeAdapter
# ---------------------------------------------------------------------------

class ForgeAdapter:
    """
    Routes games through the Forge JAR (real mode) or MockGameEngine (mock mode).
    """

    def __init__(self, mock: bool = False) -> None:
        self._mock: bool = mock or not _forge_available()
        self._proc: Optional["subprocess.Popen[bytes]"] = None
        self._sock: Optional[socket.socket] = None
        self._sock_file: Optional[_SocketFile] = None
        # game_id → (player_deck, opponent_deck) for mock games
        self._mock_decks: dict[str, tuple[list, list]] = {}
        self._mock_engine = MockGameEngine()
        self._game_counter: int = 0

        if not self._mock:
            self._launch_forge()
        else:
            logger.info("ForgeAdapter MOCK mode — set FORGE_JAR/FORGE_HOST/FORGE_PORT to enable Forge.")

    @property
    def is_mock(self) -> bool:
        return self._mock

    def start_game(self, player_deck: list, opponent_deck: list) -> str:
        game_id = str(uuid.uuid4())
        if self._mock:
            self._mock_decks[game_id] = (player_deck, opponent_deck)
            return game_id
        self._send({"type": "start_game", "game_id": game_id,
                    "player_deck": [{"name": c.name, "quantity": c.quantity} for c in player_deck],
                    "opponent_deck": [{"name": c.name, "quantity": c.quantity} for c in opponent_deck]})
        resp = self._recv()
        if resp.get("type") != "game_started":
            raise RuntimeError(f"Unexpected start_game response: {resp}")
        return game_id

    def run_game(self, game_id: str, player_agent, opponent_agent, on_the_play: bool = True) -> SimResult:
        if self._mock:
            player_deck, opponent_deck = self._mock_decks.pop(game_id, ([], []))
            self._game_counter += 1
            return self._mock_engine.run(player_deck, opponent_deck, on_the_play, self._game_counter)
        return self._live_game(game_id, player_agent, opponent_agent)

    def close(self) -> None:
        for obj in (self._sock_file, self._sock):
            if obj is not None:
                try:
                    obj.close()
                except OSError:
                    pass
        if self._proc is not None:
            self._proc.terminate()

    def _live_game(self, game_id: str, player_agent, opponent_agent) -> SimResult:
        agents = [player_agent, opponent_agent]
        turns = 0
        while True:
            msg = self._recv()
            msg_type = msg.get("type", "")
            if msg_type in ("choose_ability", "declare_attackers", "declare_blockers"):
                player_idx = int(msg.get("player", 0))
                options = msg.get("options", ["pass"])
                index = agents[player_idx](options, msg.get("state", {}))
                self._send({"type": "choice", "game_id": game_id, "index": index})
                turns = msg.get("state", {}).get("turn", turns)
            elif msg_type == "game_over":
                winner = int(msg.get("winner", 1))
                life = msg.get("life", [0, 20])
                key_cards = msg.get("key_cards_on_loss", [])
                return SimResult(
                    winner=winner,
                    turns=turns,
                    player_life=life[0] if life else 0,
                    opponent_life=life[1] if len(life) > 1 else 0,
                    key_cards_on_loss=key_cards,
                    on_the_play=False,
                )
            elif msg_type == "error":
                raise RuntimeError(f"Forge error: {msg.get('message', '?')}")

    def _launch_forge(self) -> None:
        port = int(FORGE_PORT)
        self._proc = subprocess.Popen(
            ["java", "-jar", FORGE_JAR, "--sim-server", "--port", str(port)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        logger.info("Launched Forge pid=%d", self._proc.pid)
        for _ in range(20):
            time.sleep(0.5)
            try:
                self._connect()
                return
            except OSError:
                pass
        raise RuntimeError(f"Could not connect to Forge at {FORGE_HOST}:{FORGE_PORT}")

    def _connect(self) -> None:
        self._sock = socket.create_connection((FORGE_HOST, int(FORGE_PORT)), timeout=5)
        self._sock_file = cast(_SocketFile, self._sock.makefile("rwb"))

    def _send(self, data: dict) -> None:
        assert self._sock_file is not None
        self._sock_file.write((json.dumps(data) + "\n").encode())
        self._sock_file.flush()

    def _recv(self) -> dict:
        assert self._sock_file is not None
        line = self._sock_file.readline()
        if not line:
            raise EOFError("Forge socket closed.")
        return json.loads(line.decode().strip())
