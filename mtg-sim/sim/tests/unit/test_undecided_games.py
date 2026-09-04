"""Tests that games Forge left undecided never count as wins or losses.

Forge ends a match as a draw when its sim clock expires ("Stopping slow match
as draw"). Attributing such a game to either player fabricates a result, which
is how a turn-0 draw once surfaced as a 100% win rate.
"""

from __future__ import annotations

from _sim_types import (
    UNDECIDED_WINNER,
    GameLog,
    GameLogLife,
    GameLogMulligans,
    GameLogOutcome,
    GameLogSetup,
    SimResult,
    SimResultLife,
    SimResultOutcome,
)
from forge_verbose_parser import _parse_forge_verbose_output
from game_log_emitter import format_game_log_text
from sim_batch import _batch_win_summary
from sim_statistics import MatchupConfig, compute_statistics


def _game(winner: int, index: int = 0) -> SimResult:
    """Build a minimal SimResult with the given winner index."""
    return SimResult(
        outcome=SimResultOutcome(
            winner=winner,
            timed_out=winner == UNDECIDED_WINNER,
        ),
        turns=5,
        life=SimResultLife(player=20, opponent=20),
        on_the_play=index % 2 == 0,
        log=GameLog(
            setup=GameLogSetup(game_index=index, on_the_play=index % 2 == 0),
            mulligans=GameLogMulligans(),
            player_opening_hand=[],
            turns=[],
            outcome=GameLogOutcome(
                winner=winner,
                final_turn=5,
                win_condition="draw" if winner == UNDECIDED_WINNER else "life",
            ),
            life=GameLogLife(player=20, opponent=20),
        ),
    )


def test_parser_marks_a_winnerless_game_undecided() -> None:
    """Forge output with no winner line yields no win for either side."""
    stdout = "Game 1 ended.\nStopping slow match as draw\n"
    results = _parse_forge_verbose_output(stdout, "My Deck")
    for result in results:
        assert result.winner == UNDECIDED_WINNER
        assert result.decided is False


def test_parser_is_deterministic_for_undecided_games() -> None:
    """Repeated parses of the same output agree — no random winner."""
    stdout = "Game 1 ended.\nStopping slow match as draw\n"
    winners = {
        tuple(r.winner for r in _parse_forge_verbose_output(stdout, "My Deck"))
        for _ in range(20)
    }
    assert len(winners) == 1


def test_batch_summary_sets_undecided_games_aside() -> None:
    """Undecided games are reported separately, not as wins or losses."""
    wins, losses, undecided = _batch_win_summary(
        [_game(0), _game(1), _game(UNDECIDED_WINNER)]
    )
    assert (wins, losses, undecided) == (1, 1, 1)


def test_a_single_undecided_game_is_not_a_win() -> None:
    """One drawn game must not report a 100% win rate."""
    stats = compute_statistics(
        [_game(UNDECIDED_WINNER)],
        MatchupConfig("My Deck", "Affinity", "modern"),
    )
    assert stats["winRate"] == 0.0
    assert stats["wins"] == 0
    assert stats["losses"] == 0
    assert stats["decidedGames"] == 0
    assert stats["undecidedGames"] == 1
    assert stats["games"] == 1


def test_win_rate_is_taken_over_decided_games_only() -> None:
    """Draws leave the denominator rather than diluting the win rate."""
    stats = compute_statistics(
        [_game(0, 0), _game(UNDECIDED_WINNER, 1), _game(0, 2), _game(1, 3)],
        MatchupConfig("My Deck", "Affinity", "modern"),
    )
    assert stats["winRate"] == 0.6667
    assert (stats["wins"], stats["losses"]) == (2, 1)
    assert (stats["decidedGames"], stats["undecidedGames"]) == (3, 1)


def test_play_draw_splits_exclude_undecided_games() -> None:
    """On-the-play and on-the-draw rates also ignore undecided games."""
    stats = compute_statistics(
        [_game(0, 0), _game(UNDECIDED_WINNER, 1)],
        MatchupConfig("My Deck", "Affinity", "modern"),
    )
    assert stats["onThePlay"] == {
        "wins": 1, "games": 1, "winRate": 1.0, "undecided": 0,
    }
    assert stats["onTheDraw"] == {
        "wins": 0, "games": 0, "winRate": 0.0, "undecided": 1,
    }


def test_game_log_names_no_winner_for_a_draw() -> None:
    """The emitted log must not claim either deck beat the other."""
    log = _game(UNDECIDED_WINNER).log
    assert log is not None
    text = format_game_log_text(log, "My Deck", "Affinity")
    assert "beat" not in text
    assert "no winner" in text


def test_game_log_still_names_the_winner_of_a_decided_game() -> None:
    """A real result keeps its plain-language outcome line."""
    log = _game(0).log
    assert log is not None
    assert "My Deck beat Affinity" in format_game_log_text(log, "My Deck", "Affinity")
