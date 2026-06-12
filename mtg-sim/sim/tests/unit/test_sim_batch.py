"""Unit tests for chunked simulation batching."""

from __future__ import annotations

import pytest

from _sim_types import (
    GameLog,
    GameLogLife,
    GameLogMulligans,
    GameLogOutcome,
    GameLogSetup,
    SimResult,
    SimResultLife,
    SimResultOutcome,
)
from sim_batch import (
    on_the_play_for_index,
    reindex_sim_result,
    run_chunked_simulation,
    sim_batch_size,
)


def test_on_the_play_alternates() -> None:
    """Play/draw alternates by 0-based game index."""
    assert on_the_play_for_index(0) is True
    assert on_the_play_for_index(1) is False
    assert on_the_play_for_index(2) is True


def test_reindex_sim_result() -> None:
    """Chunk-local results get global game index and on-the-play."""
    log = GameLog(
        setup=GameLogSetup(game_index=0, on_the_play=True),
        mulligans=GameLogMulligans(),
        player_opening_hand=[],
        turns=[],
        outcome=GameLogOutcome(winner=0, final_turn=5, win_condition="life"),
        life=GameLogLife(player=20, opponent=0),
    )
    result = SimResult(
        outcome=SimResultOutcome(winner=0),
        turns=5,
        life=SimResultLife(player=20, opponent=0),
        on_the_play=True,
        log=log,
    )
    reindex_sim_result(result, 5)
    assert result.on_the_play is False
    assert result.log is not None
    assert result.log.setup.game_index == 5


def test_run_chunked_simulation(monkeypatch) -> None:
    """Multiple chunks are merged with correct global indices."""
    monkeypatch.setenv("SIM_BATCH_SIZE", "2")
    calls: list[tuple[int, int]] = []

    def fake_chunk(chunk: int, start: int) -> list[SimResult]:
        calls.append((chunk, start))
        return [
            SimResult(
                outcome=SimResultOutcome(winner=0),
                turns=1,
                life=SimResultLife(),
                on_the_play=True,
            )
            for _ in range(chunk)
        ]

    results = run_chunked_simulation(5, fake_chunk, label="test")
    assert len(results) == 5
    assert calls == [(2, 0), (2, 2), (1, 4)]
    assert results[4].on_the_play is True
    assert results[3].on_the_play is False


def test_sim_batch_size_requires_env(monkeypatch) -> None:
    """SIM_BATCH_SIZE must be set in the environment."""
    monkeypatch.delenv("SIM_BATCH_SIZE", raising=False)
    with pytest.raises(RuntimeError, match="SIM_BATCH_SIZE"):
        sim_batch_size()
