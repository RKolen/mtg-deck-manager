"""
Computes aggregate statistics from a list of SimResult objects.

Produces:
  - Win rates (overall, on-play, on-draw)
  - Turn-win / turn-loss distributions
  - Top killers (opponent cards that appeared on winning board in lost games)
  - Mulligan aggregate stats
  - Life-total progression (average over games)
  - Sample game logs (first 3 complete logs kept for the UI)
  - Optional Ollama key-moment summary
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from forge_adapter import SimResult, TurnEvent

OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _half_stats(results: list["SimResult"]) -> dict:
    total = len(results)
    if total == 0:
        return {"wins": 0, "games": 0, "winRate": 0.0}
    wins = sum(1 for r in results if r.winner == 0)
    return {"wins": wins, "games": total, "winRate": round(wins / total, 4)}


def _top_killers(losses: list["SimResult"], total_losses: int) -> list[dict]:
    counter: Counter[str] = Counter()
    for r in losses:
        for card in r.key_cards_on_loss:
            counter[card] += 1
    return [
        {"card": card, "appearances": count,
         "lossContribution": round(count / max(total_losses, 1), 3)}
        for card, count in counter.most_common(5)
    ]


def _life_progression(results: list["SimResult"]) -> list[dict]:
    """
    Average life totals per turn across all games.
    Returns [{turn, avgPlayerLife, avgOppLife}]
    """
    by_turn: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for r in results:
        if r.log is None:
            continue
        for ev in r.log.turns:
            if ev.player == 0:  # record after player's turn
                by_turn[ev.turn].append((ev.life_totals[0], ev.life_totals[1]))

    rows = []
    for turn in sorted(by_turn):
        pairs = by_turn[turn]
        rows.append({
            "turn": turn,
            "avgPlayerLife": round(sum(p for p, _ in pairs) / len(pairs), 1),
            "avgOppLife": round(sum(o for _, o in pairs) / len(pairs), 1),
        })
    return rows


def _mana_efficiency(results: list["SimResult"]) -> float:
    """
    Percentage of player turns where a land was played (proxy for curve health).
    """
    total_turns = 0
    land_turns = 0
    for r in results:
        if r.log is None:
            continue
        for ev in r.log.turns:
            if ev.player != 0:
                continue
            total_turns += 1
            if any("[Land]" in p for p in ev.plays):
                land_turns += 1
    if total_turns == 0:
        return 0.0
    return round(land_turns / total_turns * 100, 1)


def _turn_breakdown(results: list["SimResult"]) -> list[dict]:
    """
    Per-turn aggregates: avg creatures in play, avg board power, avg hand size
    for the simulated player.
    """
    by_turn: dict[int, list["TurnEvent"]] = defaultdict(list)
    for r in results:
        if r.log is None:
            continue
        for ev in r.log.turns:
            if ev.player == 0:
                by_turn[ev.turn].append(ev)

    rows = []
    for turn in sorted(by_turn):
        evs = by_turn[turn]
        rows.append({
            "turn": turn,
            "avgCreatures": round(sum(e.creatures_in_play for e in evs) / len(evs), 1),
            "avgBoardPower": round(sum(e.board_power for e in evs) / len(evs), 1),
            "avgHandSize": round(sum(e.hand_size for e in evs) / len(evs), 1),
            "avgDamageDealt": round(sum(e.damage_dealt for e in evs) / len(evs), 1),
        })
    return rows


def _serialise_log(log) -> dict:
    """Convert a GameLog dataclass to a JSON-serialisable dict."""
    if log is None:
        return {}
    return {
        "gameIndex": log.game_index,
        "onThePlay": log.on_the_play,
        "playerMulligan": log.player_mulligan,
        "opponentMulligan": log.opponent_mulligan,
        "playerOpeningHand": log.player_opening_hand,
        "winner": log.winner,
        "finalTurn": log.final_turn,
        "playerFinalLife": log.player_final_life,
        "opponentFinalLife": log.opponent_final_life,
        "winCondition": log.win_condition,
        "turns": [
            {
                "turn": e.turn,
                "player": e.player,
                "manaAvailable": e.mana_available,
                "plays": e.plays,
                "damageDealt": e.damage_dealt,
                "lifeTotals": e.life_totals,
                "handSize": e.hand_size,
                "creaturesInPlay": e.creatures_in_play,
                "boardPower": e.board_power,
            }
            for e in log.turns
        ],
    }


def _build_prompt(stats: dict) -> str:
    killers = ", ".join(
        f"{k['card']} ({k['appearances']} games)" for k in stats["topKillers"]
    )
    mull = stats.get("avgMulliganCount", 0)
    return (
        f"Magic: The Gathering simulation: {stats['playerDeck']} vs "
        f"{stats['opponentArchetype']} in {stats['format']}.\n"
        f"Results: {stats['wins']}/{stats['games']} wins ({stats['winRate'] * 100:.0f}%).\n"
        f"On the play: {stats['onThePlay']['winRate'] * 100:.0f}%, "
        f"on the draw: {stats['onTheDraw']['winRate'] * 100:.0f}%.\n"
        f"Average win turn: {stats['avgTurnWin']}, loss turn: {stats['avgTurnLoss']}.\n"
        f"Average mulligans per game: {mull:.1f}.\n"
        f"Top opponent threats in losing games: {killers or 'none recorded'}.\n\n"
        "Write 2-3 short key-moment observations about this matchup. "
        "Focus on what decided games "
        "(e.g. 'Player wins X% of games where they curve out by turn 3'). "
        "One sentence each. Return as a JSON array of strings only."
    )


def _generate_key_moments(stats: dict) -> list[str]:
    if not OLLAMA_URL or not OLLAMA_MODEL:
        return []
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": _build_prompt(stats), "stream": False},
            timeout=30,
        )
        text = resp.json().get("response", "[]")
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Could not generate key moments: %s", exc)
    return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_statistics(
    results: list["SimResult"],
    player_deck_name: str,
    opponent_archetype: str,
    fmt: str,
    generate_moments: bool = True,
    sample_logs: int = 3,
) -> dict:
    """
    Compute a full simulation result dict from individual game outcomes.
    """
    total = len(results)
    if total == 0:
        return {
            "playerDeck": player_deck_name,
            "opponentArchetype": opponent_archetype,
            "format": fmt,
            "games": 0, "wins": 0, "losses": 0, "winRate": 0.0,
            "onThePlay": {"wins": 0, "games": 0, "winRate": 0.0},
            "onTheDraw": {"wins": 0, "games": 0, "winRate": 0.0},
            "avgTurnWin": 0, "avgTurnLoss": 0,
            "topKillers": [], "keyMoments": [],
            "gameLogs": [], "lifeProgression": [],
            "turnBreakdown": [], "mulliganStats": {},
        }

    wins = sum(1 for r in results if r.winner == 0)
    losses = total - wins
    on_play = [r for i, r in enumerate(results) if i % 2 == 0]
    on_draw = [r for i, r in enumerate(results) if i % 2 == 1]
    win_turns = [r.turns for r in results if r.winner == 0]
    loss_turns = [r.turns for r in results if r.winner == 1]
    losing_games = [r for r in results if r.winner == 1]

    # Mulligan stats
    player_mulls = [r.player_mulligan for r in results]
    opp_mulls = [r.opponent_mulligan for r in results]
    mull_dist = Counter(player_mulls)

    mulligan_stats = {
        "avgPlayerMulligan": round(sum(player_mulls) / total, 2),
        "avgOpponentMulligan": round(sum(opp_mulls) / total, 2),
        "distribution": {str(k): v for k, v in sorted(mull_dist.items())},
        "keepRate": round(mull_dist.get(0, 0) / total * 100, 1),
    }

    # Win condition breakdown
    win_conditions: Counter[str] = Counter(
        r.log.win_condition for r in results if r.winner == 0 and r.log
    )

    result: dict = {
        "playerDeck": player_deck_name,
        "opponentArchetype": opponent_archetype,
        "format": fmt,
        "games": total,
        "wins": wins,
        "losses": losses,
        "winRate": round(wins / total, 4),
        "onThePlay": _half_stats(on_play),
        "onTheDraw": _half_stats(on_draw),
        "avgTurnWin": round(sum(win_turns) / len(win_turns), 1) if win_turns else 0,
        "avgTurnLoss": round(sum(loss_turns) / len(loss_turns), 1) if loss_turns else 0,
        "topKillers": _top_killers(losing_games, losses),
        "mulliganStats": mulligan_stats,
        "avgMulliganCount": round(sum(player_mulls) / total, 2),
        "manaEfficiency": _mana_efficiency(results),
        "lifeProgression": _life_progression(results),
        "turnBreakdown": _turn_breakdown(results),
        "winConditions": dict(win_conditions.most_common()),
        "gameLogs": [
            _serialise_log(r.log)
            for r in results[:sample_logs]
            if r.log is not None
        ],
        "keyMoments": [],
    }

    if generate_moments:
        result["keyMoments"] = _generate_key_moments(result)

    return result
