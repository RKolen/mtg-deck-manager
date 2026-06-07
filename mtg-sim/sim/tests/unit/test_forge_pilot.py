"""Unit tests for Forge LLM pilot .dck metadata helpers."""

from __future__ import annotations

from forge_pilot import (
    ForgePilotConfig,
    format_ai_hints,
    forge_pilot_mode_for_archetype,
)


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
