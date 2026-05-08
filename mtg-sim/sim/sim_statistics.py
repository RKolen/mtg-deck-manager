"""
Computes aggregate statistics from a list of SimResult objects.

After N games are played this module:
  1. Aggregates win rates (overall, on-play, on-draw).
  2. Finds the most common opponent cards in losing games (top killers).
  3. Optionally calls Ollama to generate a plain-language key-moments summary.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from forge_adapter import SimResult

OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "")

logger = logging.getLogger(__name__)


def _half_stats(results: list["SimResult"]) -> dict:
    """Compute win/game/rate stats for one half of the game set (play vs draw)."""
    total = len(results)
    if total == 0:
        return {"wins": 0, "games": 0, "winRate": 0.0}
    wins = sum(1 for r in results if r.winner == 0)
    return {"wins": wins, "games": total, "winRate": round(wins / total, 4)}


def _top_killers(losses: list["SimResult"], total_losses: int) -> list[dict]:
    """Return the most frequently appearing opponent cards from losing games."""
    counter: Counter[str] = Counter()
    for result in losses:
        for card in result.key_cards_on_loss:
            counter[card] += 1
    return [
        {
            "card": card,
            "appearances": count,
            "lossContribution": round(count / max(total_losses, 1), 3),
        }
        for card, count in counter.most_common(5)
    ]


def _build_prompt(stats: dict) -> str:
    """Construct the Ollama prompt for key-moment generation."""
    killers = ", ".join(
        f"{k['card']} ({k['appearances']} games)" for k in stats["topKillers"]
    )
    return (
        f"Magic: The Gathering simulation: {stats['playerDeck']} vs "
        f"{stats['opponentArchetype']} in {stats['format']}.\n"
        f"Results: {stats['wins']}/{stats['games']} wins "
        f"({stats['winRate'] * 100:.0f}%).\n"
        f"On the play: {stats['onThePlay']['winRate'] * 100:.0f}%, "
        f"on the draw: {stats['onTheDraw']['winRate'] * 100:.0f}%.\n"
        f"Average win turn: {stats['avgTurnWin']}, "
        f"average loss turn: {stats['avgTurnLoss']}.\n"
        f"Top opponent threats in losing games: {killers or 'none recorded'}.\n\n"
        "Write 2-3 short key-moment observations "
        "(e.g. 'Opponent wins X% of games where ...'). "
        "One sentence each. Return as a JSON array of strings only."
    )


def _generate_key_moments(stats: dict) -> list[str]:
    """Ask Ollama to summarise key patterns from the simulation stats."""
    if not OLLAMA_URL or not OLLAMA_MODEL:
        return []
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": _build_prompt(stats), "stream": False},
            timeout=15,
        )
        text = resp.json().get("response", "[]")
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except (requests.exceptions.RequestException, ValueError, KeyError):
        pass
    return []


def compute_statistics(
    results: list["SimResult"],
    player_deck_name: str,
    opponent_archetype: str,
    fmt: str,
    generate_moments: bool = True,
) -> dict:
    """
    Compute a full simulation result dict from individual game outcomes.

    ``results[i].winner == 0`` means the player won game i.
    Even-indexed games the player goes first (on-the-play convention).
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
            "avgTurnWin": 0, "avgTurnLoss": 0, "topKillers": [], "keyMoments": [],
        }

    wins = sum(1 for r in results if r.winner == 0)
    losses = total - wins
    on_play = [r for i, r in enumerate(results) if i % 2 == 0]
    on_draw = [r for i, r in enumerate(results) if i % 2 == 1]
    win_turns = [r.turns for r in results if r.winner == 0]
    loss_turns = [r.turns for r in results if r.winner == 1]
    losing_games = [r for r in results if r.winner == 1]

    result = {
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
        "keyMoments": [],
    }

    if generate_moments:
        result["keyMoments"] = _generate_key_moments(result)

    return result
