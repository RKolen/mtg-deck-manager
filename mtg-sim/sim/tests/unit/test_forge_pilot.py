"""Unit tests for Forge LLM pilot .dck metadata helpers."""

from __future__ import annotations

from forge_pilot import (
    ForgePilotConfig,
    build_forge_cmd,
    format_ai_hints,
    forge_pilot_mode_for_archetype,
    forge_run_budget,
    forge_sim_clock,
)
from forge_pilot import _PILOT_AVG_LATENCY_RATIO, _PILOT_DECISIONS_PER_GAME


def test_format_ai_hints_empty() -> None:
    """Empty prompts produce no AiHints line."""
    assert format_ai_hints() is None
    assert format_ai_hints("", "") is None


def test_format_ai_hints_prompt_only() -> None:
    """Pilot prompt is collapsed to a single line."""
    line = format_ai_hints("You are Ruby Storm.\nWin fast.", "")
    assert line == "AiHints=PilotPrompt$You are Ruby Storm. Win fast."


def test_format_ai_hints_combo_mode() -> None:
    """PilotMode is appended when set."""
    line = format_ai_hints("combo deck", "combo")
    assert line == "AiHints=PilotPrompt$combo deck | PilotMode$combo"


def test_forge_pilot_mode_storm() -> None:
    """Storm archetypes get combo pilot mode."""
    assert forge_pilot_mode_for_archetype("Ruby Storm") == "combo"
    assert forge_pilot_mode_for_archetype("Boros Energy") == ""


def test_forge_pilot_config_active() -> None:
    """Pilot is active when URL and at least one prompt exist."""
    opp_cfg = ForgePilotConfig(
        opponent_pilot_prompt="storm",
        pilot_url="http://127.0.0.1:8010",
    )
    assert opp_cfg.pilot_active() is True
    player_cfg = ForgePilotConfig(
        player_pilot_prompt="heroic",
        pilot_url="http://127.0.0.1:8010",
    )
    assert player_cfg.pilot_active() is True
    inactive = ForgePilotConfig(pilot_url="http://127.0.0.1:8010")
    assert inactive.pilot_active() is False


def _piloted(timeout: int) -> ForgePilotConfig:
    """Build an active pilot config with the given per-call timeout."""
    return ForgePilotConfig(
        player_pilot_prompt="aggro",
        pilot_url="http://127.0.0.1:8010",
        pilot_timeout=timeout,
    )


def test_sim_clock_exceeds_a_single_pilot_call() -> None:
    """The match clock must outlast one worst-case pilot call.

    Forge's -c flag caps the whole match, so a clock at or below the per-call
    pilot budget lets the first decision end the game as a draw on turn 0.
    """
    for timeout in (30, 60, 120, 300):
        assert forge_sim_clock(_piloted(timeout)) > timeout


def test_sim_clock_scales_with_pilot_timeout() -> None:
    """A larger per-call budget buys a proportionally larger match clock."""
    assert forge_sim_clock(_piloted(300)) > forge_sim_clock(_piloted(120))


def test_sim_clock_covers_a_full_game_of_decisions() -> None:
    """The clock covers a whole game's decisions at steady-state latency.

    A piloted game needs hundreds of sidecar round trips; budgeting for only a
    few is what made every game draw on turn 0.
    """
    cfg = _piloted(120)
    steady_call = cfg.pilot_timeout * _PILOT_AVG_LATENCY_RATIO
    assert forge_sim_clock(cfg) >= steady_call * _PILOT_DECISIONS_PER_GAME


def test_builtin_ai_keeps_a_short_clock() -> None:
    """Without a pilot there are no LLM round trips to wait on."""
    assert forge_sim_clock(ForgePilotConfig()) == 120


def test_subprocess_timeout_outlasts_every_match_clock() -> None:
    """Forge must be able to stop slow games itself and still print results."""
    for n_games in (1, 3, 10):
        budget = forge_run_budget(n_games, _piloted(120))
        assert budget.subprocess_timeout > n_games * budget.clock


def test_build_forge_cmd_uses_the_derived_clock(monkeypatch) -> None:
    """The -c value on the command line is the derived clock, not a constant."""
    monkeypatch.setenv("FORGE_JAVA", "/usr/bin/java")
    cfg = _piloted(120)
    cmd = build_forge_cmd("p", "o", 1, cfg)
    assert cmd[cmd.index("-c") + 1] == str(forge_sim_clock(cfg))
