"""Format and emit per-game Forge simulation logs for debugging."""

from __future__ import annotations

import logging

from _sim_types import GameLog, SimResult

logger = logging.getLogger(__name__)


def format_game_log_text(
    log: GameLog,
    player_name: str,
    opponent_name: str,
) -> str:
    """Render a GameLog as human-readable multi-line text."""
    play_label = "on the play" if log.on_the_play else "on the draw"
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

    lines.append(_outcome_line(log, player_name, opponent_name))
    return "\n".join(lines)


def _outcome_line(log: GameLog, player_name: str, opponent_name: str) -> str:
    """Render the closing outcome line, without naming a winner for a draw."""
    life = f"final life {log.player_final_life}-{log.opponent_final_life}"
    if not log.decided:
        return (
            f"Outcome: no winner — Forge ended the game on turn "
            f"{log.final_turn} ({log.win_condition or 'unknown'}). "
            f"Excluded from the win rate | {life}"
        )
    winner = player_name if log.winner == 0 else opponent_name
    loser = opponent_name if log.winner == 0 else player_name
    return (
        f"Outcome: {winner} beat {loser} on turn {log.final_turn} "
        f"({log.win_condition or 'unknown'}) | {life}"
    )


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
