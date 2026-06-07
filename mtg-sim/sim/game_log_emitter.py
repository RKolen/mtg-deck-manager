"""Format and emit per-game simulation logs for debugging and the UI."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from _sim_types import (
    GameLog,
    GameLogLife,
    GameLogMulligans,
    GameLogOutcome,
    GameLogSetup,
    TurnBoard,
    TurnDamage,
    TurnEvent,
)

if TYPE_CHECKING:
    from engine.game.interactive import InteractiveGame
    from forge_adapter import SimResult

logger = logging.getLogger(__name__)

_PLAYER_ACTORS = frozenset({"player", "player_pilot"})
_OPPONENT_ACTORS = frozenset({"opponent", "pilot"})
_SKIP_ACTIONS = frozenset({"mulligan_bottom", "resolve", "no_draw"})


def format_game_log_text(
    log: GameLog,
    player_name: str,
    opponent_name: str,
) -> str:
    """Render a GameLog as human-readable multi-line text."""
    play_label = "on the play" if log.on_the_play else "on the draw"
    winner = player_name if log.winner == 0 else opponent_name
    loser = opponent_name if log.winner == 0 else player_name
    lines = [
        (
            f"=== Game {log.game_index + 1}: {player_name} vs {opponent_name} "
            f"({play_label}) ==="
        ),
        (
            f"Mulligans: {player_name}={log.player_mulligan}, "
            f"{opponent_name}={log.opponent_mulligan}"
        ),
    ]
    if log.player_opening_hand:
        lines.append(f"Opening hand ({player_name}): {', '.join(log.player_opening_hand)}")

    if log.pilot_notes:
        lines.append("Pilot decisions:")
        lines.extend(f"  {note}" for note in log.pilot_notes)

    for ev in log.turns:
        who = player_name if ev.player == 0 else opponent_name
        plays = ", ".join(ev.plays) if ev.plays else "pass"
        dmg = f" | {ev.damage_dealt} dmg" if ev.damage_dealt else ""
        life = f"life {ev.life_totals[0]}-{ev.life_totals[1]}"
        board = (
            f"hand {ev.hand_size}"
            + (f" ({ev.board.hand_cards})" if ev.board.hand_cards else "")
            + f" | board {ev.creatures_in_play} "
            f"(power {ev.board_power})"
        )
        lines.append(f"T{ev.turn} {who}: {plays}{dmg} | {life} | {board}")

    lines.append(
        f"Outcome: {winner} beat {loser} on turn {log.final_turn} "
        f"({log.win_condition or 'unknown'}) | "
        f"final life {log.player_final_life}-{log.opponent_final_life}"
    )
    return "\n".join(lines)


def emit_batch_game_logs(
    results: list[SimResult],
    player_name: str,
    opponent_name: str,
) -> None:
    """Write full game logs for one completed sim batch to the service logger."""
    for result in results:
        if result.log is None:
            continue
        logger.info(
            "\n%s",
            format_game_log_text(result.log, player_name, opponent_name),
        )


def emit_game_logs(
    results: list[SimResult],
    player_name: str,
    opponent_name: str,
    limit: int = 3,
) -> None:
    """Write sample game logs to the sim service logger (.sim.log)."""
    emitted = 0
    for result in results:
        if result.log is None:
            continue
        logger.info(
            "\n%s",
            format_game_log_text(result.log, player_name, opponent_name),
        )
        emitted += 1
        if emitted >= limit:
            break


def emit_interactive_log(
    game: InteractiveGame,
    player_name: str,
    opponent_name: str,
    game_index: int,
) -> None:
    """Write the raw interactive engine log for one headless game."""
    lines = [
        (
            f"=== Game {game_index + 1}: {player_name} vs {opponent_name} "
            f"({'on the play' if game.on_the_play else 'on the draw'}) "
            "[python engine] ==="
        ),
        f"Player mulligans: {game.mulligans_taken}",
    ]
    for entry in game.state.log:
        lines.append(f"T{entry.turn} {entry.actor}/{entry.action}: {entry.detail}")
    winner = game.winner
    if winner is not None:
        who = player_name if winner == 0 else opponent_name
        lines.append(
            f"Outcome: {who} won on turn {game.turn} | "
            f"life {game.state.players[0].life}-{game.state.players[1].life}"
        )
    logger.info("\n%s", "\n".join(lines))


def _actor_player_idx(actor: str) -> int | None:
    if actor in _PLAYER_ACTORS:
        return 0
    if actor in _OPPONENT_ACTORS:
        return 1
    return None


def _play_line(action: str, detail: str) -> str | None:
    if action in _SKIP_ACTIONS:
        return None
    if action == "land":
        return f"{detail} [Land]"
    if action == "pick":
        return f"[Pilot] {detail}"
    if action in ("keep", "mulligan"):
        return f"[{action}] {detail}"
    if detail:
        return detail
    return f"[{action}]"


def _attack_damage(detail: str) -> int:
    match = re.search(r"(\d+)\s+damage", detail)
    return int(match.group(1)) if match else 0


@dataclass
class _TurnBucket:
    """Accumulates log lines for one player's turn."""

    turn: int
    player: int
    plays: list[str] = field(default_factory=list)
    damage: int = 0


class _InteractiveLogBuilder:
    """Build TurnEvent rows from InteractiveGame log entries."""

    def __init__(self, game: InteractiveGame) -> None:
        self._game = game
        self._life_p = 20
        self._life_o = 20
        self._events: list[TurnEvent] = []
        self._bucket: _TurnBucket | None = None

    def _board_snapshot(self, player_idx: int) -> TurnBoard:
        zones = self._game.state.zones
        return TurnBoard(
            hand_size=len(zones.player_zones[player_idx].hand),
            creatures_in_play=len(zones.permanents_of(player_idx)),
            power=0,
        )

    def _flush(self) -> None:
        if self._bucket is None or not self._bucket.plays:
            self._bucket = None
            return
        player_idx = self._bucket.player
        zones = self._game.state.zones
        self._events.append(
            TurnEvent(
                turn=self._bucket.turn,
                player=player_idx,
                mana_available=len(zones.untapped_lands_of(player_idx)),
                plays=list(self._bucket.plays),
                life_totals=[self._life_p, self._life_o],
                board=self._board_snapshot(player_idx),
                damage=TurnDamage(
                    total=self._bucket.damage,
                    combat=self._bucket.damage,
                    noncombat=0,
                ),
            )
        )
        self._bucket = None

    def feed(self, actor: str, action: str, detail: str, turn: int) -> None:
        """Consume one log entry."""
        player_idx = _actor_player_idx(actor)
        if player_idx is None:
            return
        line = _play_line(action, detail)
        if line is None:
            return
        if self._bucket is None or self._bucket.player != player_idx or self._bucket.turn != turn:
            self._flush()
            self._bucket = _TurnBucket(turn=turn, player=player_idx)
        assert self._bucket is not None
        self._bucket.plays.append(line)
        if action == "attack":
            dmg = _attack_damage(detail)
            self._bucket.damage += dmg
            if player_idx == 0:
                self._life_o = max(0, self._life_o - dmg)
            else:
                self._life_p = max(0, self._life_p - dmg)

    def events(self) -> list[TurnEvent]:
        """Return accumulated turn events."""
        self._flush()
        return list(self._events)


def build_interactive_game_log(
    game: InteractiveGame,
    game_index: int,
    on_the_play: bool,
    opponent_mulligans: int,
    opening_hand: list[str],
) -> GameLog:
    """Build a GameLog from an InteractiveGame session for API statistics."""
    builder = _InteractiveLogBuilder(game)
    for entry in game.state.log:
        builder.feed(entry.actor, entry.action, entry.detail, entry.turn)

    winner = game.winner if game.winner is not None else 0
    win_condition = "turn_cap" if game.phase != "game_over" else "life_loss"

    return GameLog(
        setup=GameLogSetup(game_index=game_index, on_the_play=on_the_play),
        mulligans=GameLogMulligans(
            player=game.mulligans_taken,
            opponent=opponent_mulligans,
        ),
        player_opening_hand=opening_hand,
        turns=builder.events(),
        outcome=GameLogOutcome(
            winner=winner,
            final_turn=game.turn,
            win_condition=win_condition,
        ),
        life=GameLogLife(
            player=game.state.players[0].life,
            opponent=game.state.players[1].life,
        ),
    )
