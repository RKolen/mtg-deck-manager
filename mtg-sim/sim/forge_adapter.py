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
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from _sim_types import (
    GameLog,
    GameLogLife,
    GameLogMulligans,
    GameLogOutcome,
    GameLogSetup,
    SimResult,
    SimResultLife,
    SimResultMulligans,
    SimResultOutcome,
    TurnBoard,
    TurnDamage,
    TurnEvent,
    _GameOutcome,
)
from forge_verbose_parser import _parse_forge_verbose_output
from forge_pilot import (
    ForgePilotConfig,
    ForgeSimOptions,
    build_forge_cmd,
    deck_ai_hints,
    forge_pilot_mode_for_archetype,
    invoke_forge,
)
from game_log_emitter import emit_batch_game_logs
from sim_batch import on_the_play_for_index, run_chunked_simulation

if TYPE_CHECKING:
    from deck_registry import CardInfo

logger = logging.getLogger(__name__)

FORGE_JAR: str = os.environ.get("FORGE_JAR", "")
FORGE_JAVA: str = os.environ.get("FORGE_JAVA", "java")


def forge_jar_available() -> bool:
    """Return True when FORGE_JAR points to an existing file."""
    return bool(FORGE_JAR and os.path.isfile(FORGE_JAR))


# ---------------------------------------------------------------------------
# .dck export
# ---------------------------------------------------------------------------

def _write_dck(
    cards: list["CardInfo"],
    name: str,
    path: pathlib.Path,
    ai_hints_line: Optional[str] = None,
) -> None:
    """Write a list of CardInfo objects as a Forge .dck file."""
    lines = ["[metadata]", f"Name={name}"]
    if ai_hints_line:
        lines.append(ai_hints_line)
    lines.append("[Main]")
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

    Forge prints per game (even in quiet -q mode):
      Game Outcome: Turn N          ← turn the game ended on
      Game Outcome: <winner> has won because ...
      Match Result: ...

      Game Result: Game N ended in X ms. PlayerName has won!
      Game Result: Game N ended in a Draw! Took X ms.

    We walk the output line by line, tracking the most recent turn number
    seen before each "Game Result:" line.
    """
    results: list[SimResult] = []
    turn_pattern = re.compile(r"Game Outcome: Turn (\d+)", re.IGNORECASE)
    result_pattern = re.compile(
        r"Game Result: Game (\d+) ended.*?(?:(\S.*?) has won!|a Draw)",
        re.IGNORECASE,
    )
    current_turn: Optional[int] = None
    for line in stdout.splitlines():
        turn_match = turn_pattern.match(line.strip())
        if turn_match:
            current_turn = int(turn_match.group(1))
            continue
        result_match = result_pattern.search(line)
        if result_match:
            game_num = int(result_match.group(1))
            winner_name = result_match.group(2)
            on_the_play = game_num % 2 == 1
            if winner_name is None:
                winner = random.randint(0, 1)  # draw → coin flip for stats
            else:
                # Forge prefixes "Ai(N)-" to the deck name in game results.
                winner = 0 if player_name in winner_name else 1
            results.append(SimResult(
                outcome=SimResultOutcome(winner=winner, timed_out=False),
                turns=current_turn,
                life=SimResultLife(player=0, opponent=0),
                on_the_play=on_the_play,
            ))
            current_turn = None  # reset for next game
    return results


_FORGE_DECK_DIR = pathlib.Path.home() / ".forge" / "decks" / "constructed"


def _log_forge_run(
    player_name: str,
    opponent_name: str,
    n_games: int,
    pilot_cfg: ForgePilotConfig,
) -> None:
    """Log whether this batch uses LLM pilot or built-in AI."""
    if pilot_cfg.pilot_active():
        logger.info(
            "Running Forge: %s vs %s, %d games — LLM pilot "
            "(player %d chars, opponent %d chars) via %s (timeout %ds)",
            player_name,
            opponent_name,
            n_games,
            len(pilot_cfg.player_pilot_prompt.strip()),
            len(pilot_cfg.opponent_pilot_prompt.strip()),
            pilot_cfg.pilot_url,
            pilot_cfg.pilot_timeout,
        )
        return
    logger.info(
        "Running Forge: %s vs %s, %d games — Forge built-in AI only",
        player_name, opponent_name, n_games,
    )


def _forge_file_slug(display_name: str, run_id: str, fallback: str) -> str:
    """Build a unique Forge .dck filename stem from a human deck title."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", display_name).strip("_")[:48]
    return f"{slug or fallback}_{run_id}"


@dataclass(frozen=True)
class ForgeDeckNames:
    """Human-readable deck titles written into Forge .dck metadata."""

    player: str
    opponent: str


def _materialize_forge_decks(
    player_cards: list["CardInfo"],
    opponent_cards: list["CardInfo"],
    pilot_cfg: ForgePilotConfig,
    run_id: str,
    deck_names: ForgeDeckNames,
) -> tuple[str, str, pathlib.Path, pathlib.Path]:
    """Write temporary .dck files and return deck file stems and paths."""
    combo_mode = forge_pilot_mode_for_archetype(pilot_cfg.opponent_archetype)
    p_slug = _forge_file_slug(deck_names.player, run_id, "player")
    o_slug = _forge_file_slug(deck_names.opponent, run_id, "opponent")
    p_dck = _FORGE_DECK_DIR / f"{p_slug}.dck"
    o_dck = _FORGE_DECK_DIR / f"{o_slug}.dck"
    p_hints = deck_ai_hints(pilot_cfg.player_pilot_prompt)
    o_hints = deck_ai_hints(
        pilot_cfg.opponent_pilot_prompt,
        combo_mode,
    )
    _write_dck(player_cards, deck_names.player, p_dck, p_hints)
    _write_dck(opponent_cards, deck_names.opponent, o_dck, o_hints)
    return p_slug, o_slug, p_dck, o_dck


def run_forge_batch(
    player_cards: list["CardInfo"],
    opponent_cards: list["CardInfo"],
    n_games: int,
    *,
    deck_names: tuple[str, str] = ("Player", "Opponent"),
    pilot: Optional[ForgePilotConfig] = None,
) -> list[SimResult]:
    """
    Run n_games via Forge's built-in sim command.

    Writes temporary .dck files into ~/.forge/decks/constructed/ (where Forge's
    deckFromCommandLineParameter expects them), invokes the JAR as a subprocess,
    and parses stdout for per-game winners.
    """
    player_name, opponent_name = deck_names
    pilot_cfg = pilot or ForgePilotConfig()
    _FORGE_DECK_DIR.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    p_slug, o_slug, p_dck, o_dck = _materialize_forge_decks(
        player_cards, opponent_cards, pilot_cfg, run_id,
        ForgeDeckNames(player=player_name, opponent=opponent_name),
    )

    try:
        _log_forge_run(player_name, opponent_name, n_games, pilot_cfg)
        stdout = invoke_forge(
            build_forge_cmd(p_slug, o_slug, n_games, pilot_cfg),
            n_games,
        )
        if not stdout:
            return []

        results = _parse_forge_verbose_output(stdout, player_name)
        if not results:
            logger.warning(
                "Forge produced no parseable results.\nstdout: %s", stdout[:1000]
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
        life_totals=[side.life, 0],   # opponent life set by caller
        board=TurnBoard(
            hand_size=len(side.hand),
            creatures_in_play=len(side.creatures),
            power=side.attack_power(),
        ),
        damage=TurnDamage(
            total=damage,
            combat=damage,  # mock engine damage is always from combat
            noncombat=0,
        ),
    )


class MockGameEngine:
    """
    Simulates MTG games from actual deck card data without the Forge rules engine.

    Models: mulligan decisions, land drops, spell casting, summoning sickness,
    trample, and simplified combat.
    """

    MAX_TURNS = 12

    def _build_result(
        self,
        player: "_BoardSide",
        opponent: "_BoardSide",
        outcome: "_GameOutcome",
    ) -> SimResult:
        """Assemble the final SimResult from accumulated game state."""
        key_cards: list[str] = []
        if outcome.winner == 1 and opponent.creatures:
            key_cards = random.sample(
                [c.name for c in opponent.creatures], k=min(3, len(opponent.creatures))
            )
        log = GameLog(
            setup=GameLogSetup(game_index=outcome.game_index, on_the_play=outcome.on_the_play),
            mulligans=GameLogMulligans(
                player=player.mulligan_count,
                opponent=opponent.mulligan_count,
            ),
            player_opening_hand=outcome.player_opening_hand,
            turns=outcome.turn_events,
            outcome=GameLogOutcome(
                winner=outcome.winner,
                final_turn=outcome.final_turn,
                win_condition=outcome.win_condition,
            ),
            life=GameLogLife(player=player.life, opponent=opponent.life),
        )
        return SimResult(
            outcome=SimResultOutcome(
                winner=outcome.winner,
                timed_out=outcome.win_condition == "turn_cap",
            ),
            turns=outcome.final_turn,
            life=SimResultLife(player=player.life, opponent=opponent.life),
            key_cards_on_loss=key_cards,
            on_the_play=outcome.on_the_play,
            mulligans=SimResultMulligans(
                player=player.mulligan_count,
                opponent=opponent.mulligan_count,
            ),
            log=log,
        )

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
        win_condition = "turn_cap"

        for turn in range(1, self.MAX_TURNS + 1):
            player.clear_sickness()
            opponent.clear_sickness()

            result = self._run_half_turn(player, opponent, turn, 0, turn == 1 and on_the_play)
            turn_events.append(result)
            if opponent.life <= 0:
                winner, final_turn, win_condition = 0, turn, self._classify_win(player_cards)
                break

            result = self._run_half_turn(opponent, player, turn, 1, False)
            turn_events.append(result)
            if player.life <= 0:
                winner, final_turn, win_condition = 1, turn, self._classify_win(opponent_cards)
                break
        else:
            winner = 0 if player.life > opponent.life else 1

        game_outcome = _GameOutcome(
            winner=winner,
            final_turn=final_turn,
            win_condition=win_condition,
            player_opening_hand=player_opening_hand,
            turn_events=turn_events,
            on_the_play=on_the_play,
            game_index=game_index,
        )
        return self._build_result(player, opponent, game_outcome)

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
        self._mock = not forge_jar_available()
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
        *,
        options: Optional[ForgeSimOptions] = None,
    ) -> list[SimResult]:
        """
        Run n_games and return one SimResult per game.

        Uses Forge when available, MockGameEngine otherwise.
        """
        opts = options or ForgeSimOptions()
        player_name, opponent_name = opts.deck_names

        def after_batch(batch: list[SimResult]) -> None:
            emit_batch_game_logs(batch, player_name, opponent_name)

        if not self._mock:
            results = run_chunked_simulation(
                n_games,
                lambda chunk, start: run_forge_batch(
                    player_cards,
                    opponent_cards,
                    chunk,
                    deck_names=opts.deck_names,
                    pilot=opts.pilot,
                ),
                label=f"{player_name} vs {opponent_name}",
                after_batch=after_batch,
            )
            if results:
                return results
            logger.warning("Forge returned no results — falling back to mock engine")

        return run_chunked_simulation(
            n_games,
            lambda chunk, start: [
                self._mock_engine.run(
                    player_cards, opponent_cards,
                    on_the_play=on_the_play_for_index(start + i),
                    game_index=start + i,
                )
                for i in range(chunk)
            ],
            label=f"{player_name} vs {opponent_name}",
            after_batch=after_batch,
        )

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
