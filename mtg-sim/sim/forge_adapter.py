"""
ForgeAdapter — runs MTG simulations via Forge or the built-in mock engine.

Real mode (FORGE_JAR set):
  Writes temporary .dck files and invokes Forge's built-in 'sim' command as a
  subprocess.  Forge handles full MTG rules; we parse its stdout for results.

Mock mode (FORGE_JAR not set):
  Uses MockGameEngine — a lightweight Python engine that models land drops,
  spell casting, combat and mulligan decisions from actual card CMC/type data.

Deck format (.dck):
  [metadata]
  Name=DeckName
  [Main]
  4 Card Name
  [Sideboard]
  2 Sideboard Card
"""

from __future__ import annotations

import logging
import os
import pathlib
import random
import re
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from deck_registry import CardInfo

logger = logging.getLogger(__name__)

FORGE_JAR: str = os.environ.get("FORGE_JAR", "")
FORGE_JAVA: str = os.environ.get("FORGE_JAVA", "java")


def _forge_available() -> bool:
    """Return True when FORGE_JAR points to an existing file."""
    return bool(FORGE_JAR and os.path.isfile(FORGE_JAR))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TurnEvent:
    """One player's full turn within a game."""

    turn: int
    player: int
    mana_available: int
    plays: list[str]
    damage_dealt: int
    life_totals: list[int]
    hand_size: int
    creatures_in_play: int
    board_power: int


@dataclass
class GameLog:
    """Complete record of a single simulated game."""

    game_index: int
    on_the_play: bool
    player_mulligan: int
    opponent_mulligan: int
    player_opening_hand: list[str]
    turns: list[TurnEvent]
    winner: int
    final_turn: int
    player_final_life: int
    opponent_final_life: int
    win_condition: str


@dataclass
class SimResult:
    """Outcome of a single simulated game — passed to sim_statistics."""

    winner: int
    turns: Optional[int]
    player_life: int
    opponent_life: int
    key_cards_on_loss: list[str] = field(default_factory=list)
    on_the_play: bool = True
    player_mulligan: int = 0
    opponent_mulligan: int = 0
    log: Optional[GameLog] = None

    @property
    def player_won(self) -> bool:
        """True when the player (index 0) won this game."""
        return self.winner == 0


# ---------------------------------------------------------------------------
# .dck export
# ---------------------------------------------------------------------------

def _write_dck(cards: list["CardInfo"], name: str, path: pathlib.Path) -> None:
    """Write a list of CardInfo objects as a Forge .dck file."""
    lines = ["[metadata]", f"Name={name}", "[Main]"]
    for c in cards:
        if not c.sideboard:
            lines.append(f"{c.quantity} {c.name}")
    sideboard = [c for c in cards if c.sideboard]
    if sideboard:
        lines.append("[Sideboard]")
        for c in sideboard:
            lines.append(f"{c.quantity} {c.name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Forge subprocess simulation
# ---------------------------------------------------------------------------

def _parse_forge_output(stdout: str, player_name: str) -> list[SimResult]:
    """
    Parse Forge sim stdout into SimResult objects.

    Forge prints one line per game:
      Game Result: Game N ended in X ms. PlayerName has won!
      Game Result: Game N ended in a Draw! Took X ms.
    """
    results: list[SimResult] = []
    pattern = re.compile(
        r"Game Result: Game (\d+) ended.*?(?:(\S.*?) has won!|a Draw)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(stdout):
        game_num = int(match.group(1))
        winner_name = match.group(2)
        on_the_play = game_num % 2 == 1
        if winner_name is None:
            winner = random.randint(0, 1)  # draw → coin flip for stats
        else:
            # Forge prefixes "Ai(N)-" to the deck name in game results.
            winner = 0 if player_name in winner_name else 1
        results.append(SimResult(
            winner=winner,
            turns=None,
            player_life=0,
            opponent_life=0,
            on_the_play=on_the_play,
        ))
    return results


_FORGE_DECK_DIR = pathlib.Path.home() / ".forge" / "decks" / "constructed"


def run_forge_batch(
    player_cards: list["CardInfo"],
    opponent_cards: list["CardInfo"],
    n_games: int,
    player_name: str = "Player",
    opponent_name: str = "Opponent",
) -> list[SimResult]:
    """
    Run n_games via Forge's built-in sim command.

    Writes temporary .dck files into ~/.forge/decks/constructed/ (where Forge's
    deckFromCommandLineParameter expects them), invokes the JAR as a subprocess,
    and parses stdout for per-game winners.
    """
    _FORGE_DECK_DIR.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    p_name = f"sim_p_{run_id}"
    o_name = f"sim_o_{run_id}"
    p_dck = _FORGE_DECK_DIR / f"{p_name}.dck"
    o_dck = _FORGE_DECK_DIR / f"{o_name}.dck"

    try:
        _write_dck(player_cards, player_name, p_dck)
        _write_dck(opponent_cards, opponent_name, o_dck)

        # Forge's sim deckFromCommandLineParameter prepends DECK_CONSTRUCTED_DIR
        # to the filename when the name ends with a 3-char extension.
        cmd = [
            FORGE_JAVA, "-jar", FORGE_JAR,
            "sim",
            "-d", f"{p_name}.dck", f"{o_name}.dck",
            "-n", str(n_games),
            "-q",
            "-c", "60",
        ]
        logger.info("Running Forge: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=n_games * 90,
                check=False,
                cwd=str(pathlib.Path(FORGE_JAR).parent),
            )
        except subprocess.TimeoutExpired:
            logger.error("Forge simulation timed out after %d games", n_games)
            return []
        except FileNotFoundError:
            logger.error("Java not found. Set FORGE_JAVA to the java binary path.")
            return []

        if proc.returncode != 0:
            logger.error("Forge exited %d: %s", proc.returncode, proc.stderr[:500])

        results = _parse_forge_output(proc.stdout, player_name)
        if not results:
            logger.warning(
                "Forge produced no parseable results.\nstdout: %s", proc.stdout[:1000]
            )
        return results
    finally:
        p_dck.unlink(missing_ok=True)
        o_dck.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Mock game engine (used when Forge is not available)
# ---------------------------------------------------------------------------

class _BoardSide:
    """Tracks one player's in-game state for the mock engine."""

    def __init__(self, cards: list["CardInfo"]) -> None:
        """Initialise with a shuffled library of expanded card instances."""
        self.library: list["CardInfo"] = cards.copy()
        random.shuffle(self.library)
        self.hand: list["CardInfo"] = []
        self.lands: list["CardInfo"] = []
        self.creatures: list["CardInfo"] = []
        self.fresh_creatures: list["CardInfo"] = []
        self.life: int = 20
        self.mulligan_count: int = 0

    def draw_opening_hand(self) -> None:
        """Draw 7 cards and mulligan until hand quality is acceptable."""
        for attempt in range(4):
            hand_size = 7 - attempt
            random.shuffle(self.library)
            hand = self.library[:hand_size]
            land_count = sum(1 for c in hand if c.is_land)
            lo = 2 if hand_size >= 6 else 1
            hi = min(hand_size - 1, 5)
            if lo <= land_count <= hi or attempt == 3:
                self.hand = list(hand)
                self.library = self.library[hand_size:]
                self.mulligan_count = attempt
                return

    def draw(self) -> None:
        """Draw one card from the top of the library."""
        if self.library:
            self.hand.append(self.library.pop(0))

    def clear_sickness(self) -> None:
        """Remove summoning sickness from creatures that entered last turn."""
        self.fresh_creatures.clear()

    def play_land(self) -> Optional["CardInfo"]:
        """Play the first land found in hand; return it or None."""
        for c in self.hand:
            if c.is_land:
                self.hand.remove(c)
                self.lands.append(c)
                return c
        return None

    def cast_spells(self) -> list["CardInfo"]:
        """Cast as many affordable non-land spells as possible (cheapest first)."""
        mana = len(self.lands)
        spent = 0
        cast: list["CardInfo"] = []
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

    def attackers(self) -> list["CardInfo"]:
        """Return creatures not affected by summoning sickness."""
        return [c for c in self.creatures if c not in self.fresh_creatures]

    def attack_power(self) -> int:
        """Return total power of eligible attackers."""
        return sum(c.numeric_power for c in self.attackers())

    def take_damage(self, damage: int) -> None:
        """Reduce life total by damage, minimum zero."""
        self.life = max(0, self.life - damage)


def _resolve_mock_combat(attacker_side: _BoardSide, defender_side: _BoardSide) -> int:
    """
    Simplified combat: all eligible creatures attack, defender blocks to absorb
    as much damage as possible.  Returns damage dealt to the defending player.
    """
    attackers = attacker_side.attackers()
    if not attackers:
        return 0

    defenders = sorted(defender_side.creatures, key=lambda c: c.numeric_toughness, reverse=True)
    sorted_attackers = sorted(attackers, key=lambda c: c.numeric_power, reverse=True)
    remaining_block = sum(c.numeric_toughness for c in defenders)
    damage_through = 0

    for atk in sorted_attackers:
        has_trample = "trample" in (atk.oracle_text or "").lower()
        if remaining_block > 0:
            absorbed = min(remaining_block, atk.numeric_power)
            remaining_block -= absorbed
            if has_trample:
                damage_through += atk.numeric_power - absorbed
        else:
            damage_through += atk.numeric_power

    return max(0, damage_through)


def _make_turn_event(side: _BoardSide, turn: int, player: int,
                     plays: list[str], damage: int) -> TurnEvent:
    """Build a TurnEvent snapshot from the current board state."""
    return TurnEvent(
        turn=turn,
        player=player,
        mana_available=len(side.lands),
        plays=plays,
        damage_dealt=damage,
        life_totals=[side.life, 0],   # opponent life set by caller
        hand_size=len(side.hand),
        creatures_in_play=len(side.creatures),
        board_power=side.attack_power(),
    )


class MockGameEngine:
    """
    Simulates MTG games from actual deck card data without the Forge rules engine.

    Models: mulligan decisions, land drops, spell casting, summoning sickness,
    trample, and simplified combat.
    """

    MAX_TURNS = 12

    def run(
        self,
        player_cards: list["CardInfo"],
        opponent_cards: list["CardInfo"],
        on_the_play: bool,
        game_index: int = 0,
    ) -> SimResult:
        """Simulate one full game and return the outcome."""
        player = _BoardSide(self._expand(player_cards))
        opponent = _BoardSide(self._expand(opponent_cards))
        player.draw_opening_hand()
        opponent.draw_opening_hand()
        player_opening_hand = [c.name for c in player.hand]
        turn_events: list[TurnEvent] = []

        winner = 1
        final_turn = self.MAX_TURNS
        win_condition = "time"

        for turn in range(1, self.MAX_TURNS + 1):
            player.clear_sickness()
            opponent.clear_sickness()

            # Player's turn (no draw on turn 1 when on the play)
            result = self._run_half_turn(player, opponent, turn, 0, turn == 1 and on_the_play)
            turn_events.append(result)
            if opponent.life <= 0:
                winner, final_turn, win_condition = 0, turn, self._classify_win(player_cards)
                break

            # Opponent's turn
            result = self._run_half_turn(opponent, player, turn, 1, False)
            turn_events.append(result)
            if player.life <= 0:
                winner, final_turn, win_condition = 1, turn, self._classify_win(opponent_cards)
                break
        else:
            winner = 0 if player.life > opponent.life else 1

        key_cards: list[str] = []
        if winner == 1 and opponent.creatures:
            key_cards = random.sample(
                [c.name for c in opponent.creatures], k=min(3, len(opponent.creatures))
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
            log=GameLog(
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
            ),
        )

    @staticmethod
    def _run_half_turn(
        active: _BoardSide,
        passive: _BoardSide,
        turn: int,
        player_idx: int,
        skip_draw: bool,
    ) -> TurnEvent:
        """Execute one player's half-turn; return the resulting TurnEvent."""
        if not skip_draw:
            active.draw()
        land = active.play_land()
        cast = active.cast_spells()

        plays: list[str] = []
        if land:
            plays.append(f"[Land] {land.name}")
        for c in cast:
            plays.append(f"[{c.short_type()}] {c.name}")

        damage = _resolve_mock_combat(active, passive)
        passive.take_damage(damage)

        ev = _make_turn_event(active, turn, player_idx, plays, damage)
        ev.life_totals = [active.life, passive.life]
        return ev

    @staticmethod
    def expand_deck(cards: list["CardInfo"]) -> list["CardInfo"]:
        """Expand a compact card list (with quantities) into individual instances."""
        result = []
        for c in cards:
            if not c.sideboard:
                result.extend([c] * c.quantity)
        return result

    @staticmethod
    def _expand(cards: list["CardInfo"]) -> list["CardInfo"]:
        """Private alias kept for internal use."""
        return MockGameEngine.expand_deck(cards)

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
# ForgeAdapter — public interface
# ---------------------------------------------------------------------------

class ForgeAdapter:
    """
    Routes batch simulations through Forge (real mode) or MockGameEngine.

    Real mode: FORGE_JAR must point to the built forge-gui-desktop JAR.
    Mock mode: used automatically when FORGE_JAR is not set or the file
               does not exist.
    """

    def __init__(self) -> None:
        """Initialise, selecting Forge or mock mode based on environment."""
        self._mock = not _forge_available()
        self._mock_engine = MockGameEngine()
        self._mock_decks: dict[str, tuple[list, list]] = {}
        self._game_counter: int = 0

        if self._mock:
            logger.info(
                "ForgeAdapter MOCK mode — set FORGE_JAR to the Forge desktop JAR "
                "and ensure 'java' is on PATH to enable real simulation."
            )
        else:
            logger.info("ForgeAdapter FORGE mode — JAR: %s", FORGE_JAR)

    @property
    def is_mock(self) -> bool:
        """True when running without the Forge JAR."""
        return self._mock

    def run_simulation(
        self,
        player_cards: list["CardInfo"],
        opponent_cards: list["CardInfo"],
        n_games: int,
        deck_names: tuple[str, str] = ("Player", "Opponent"),
    ) -> list[SimResult]:
        """
        Run n_games and return one SimResult per game.

        Uses Forge when available, MockGameEngine otherwise.
        deck_names is (player_name, opponent_name) used for .dck metadata.
        """
        player_name, opponent_name = deck_names
        if not self._mock:
            results = run_forge_batch(
                player_cards, opponent_cards, n_games, player_name, opponent_name,
            )
            if results:
                return results
            logger.warning("Forge returned no results — falling back to mock engine")

        return [
            self._mock_engine.run(
                player_cards, opponent_cards,
                on_the_play=i % 2 == 0,
                game_index=i,
            )
            for i in range(n_games)
        ]

    # ------------------------------------------------------------------
    # Legacy single-game API retained for the interactive game path
    # ------------------------------------------------------------------

    def start_game(self, player_deck: list, opponent_deck: list) -> str:
        """Register a game session and return its ID."""
        game_id = str(uuid.uuid4())
        self._mock_decks[game_id] = (player_deck, opponent_deck)
        return game_id

    def run_game(self, game_id: str, on_the_play: bool = True) -> SimResult:
        """Run one registered game via MockGameEngine and return the result."""
        player_deck, opponent_deck = self._mock_decks.pop(game_id, ([], []))
        self._game_counter += 1
        return self._mock_engine.run(player_deck, opponent_deck, on_the_play, self._game_counter)

    def close(self) -> None:
        """No-op; provided for interface symmetry."""
