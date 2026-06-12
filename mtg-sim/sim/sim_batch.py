"""Chunk long simulation runs into smaller Forge/Python batches."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Optional

from _sim_types import GameLogSetup, SimResult
from env_loader import require_env_int

logger = logging.getLogger(__name__)


def sim_batch_size() -> int:
    """Games per Forge/Python subprocess (env SIM_BATCH_SIZE)."""
    size = require_env_int("SIM_BATCH_SIZE")
    return max(1, min(size, 50))


def on_the_play_for_index(game_index: int) -> bool:
    """True when the simulated player is on the play for this 0-based game index."""
    return game_index % 2 == 0


def reindex_sim_result(result: SimResult, game_index: int) -> SimResult:
    """Fix game_index and on-the-play after a chunked Forge run (local 1..N)."""
    on_play = on_the_play_for_index(game_index)
    result.on_the_play = on_play
    if result.log is not None:
        result.log.setup = GameLogSetup(
            game_index=game_index,
            on_the_play=on_play,
        )
    return result


def _batch_win_summary(results: list[SimResult]) -> tuple[int, int]:
    wins = sum(1 for r in results if r.winner == 0)
    return wins, len(results) - wins


def log_batch_progress(
    label: str,
    completed: int,
    total: int,
    results: list[SimResult],
) -> None:
    """Log running win-rate after each batch completes."""
    wins, losses = _batch_win_summary(results)
    rate = (100.0 * wins / len(results)) if results else 0.0
    logger.info(
        "Sim batch done: %s — %d/%d games (%.1f%% win rate, %dW-%dL so far)",
        label,
        completed,
        total,
        rate,
        wins,
        losses,
    )


def run_chunked_simulation(
    n_games: int,
    run_chunk: Callable[[int, int], list[SimResult]],
    *,
    label: str = "matchup",
    after_batch: Optional[Callable[[list[SimResult]], None]] = None,
) -> list[SimResult]:
    """Run ``n_games`` in batches of ``sim_batch_size()``, logging after each."""
    batch_size = sim_batch_size()
    all_results: list[SimResult] = []
    start = 0

    if n_games > batch_size:
        logger.info(
            "Sim chunked: %d games in batches of %d (%d Forge/Python runs)",
            n_games,
            batch_size,
            (n_games + batch_size - 1) // batch_size,
        )

    while start < n_games:
        chunk = min(batch_size, n_games - start)
        logger.info("Sim batch starting: games %d–%d of %d", start + 1, start + chunk, n_games)
        batch = run_chunk(chunk, start)
        if not batch:
            logger.error("Sim batch returned no results at game %d", start + 1)
            break
        for offset, result in enumerate(batch):
            reindex_sim_result(result, start + offset)
        all_results.extend(batch)
        start += len(batch)
        log_batch_progress(label, start, n_games, all_results)
        if after_batch is not None:
            after_batch(batch)

    return all_results
