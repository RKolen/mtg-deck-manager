"""Unit tests for caveman pilot prompt compression."""

from __future__ import annotations

from caveman_compress import (
    compress_pilot_prompt,
    compress_pilot_prompt_rules,
    prompt_preview,
)


def test_rules_compress_drops_filler(monkeypatch) -> None:
    """Filler words and articles are stripped from prose."""
    monkeypatch.setenv("CAVEMAN_PILOT", "rules")
    raw = (
        "You are piloting a deck that basically just wants to attack with "
        "the biggest creature on the board."
    )
    out = compress_pilot_prompt_rules(raw)
    assert "basically" not in out.lower()
    assert "just" not in out.split()
    assert "Pilot" in out or "pilot" in out.lower()


def test_compress_skips_short_text(monkeypatch) -> None:
    """Short field notes are left unchanged."""
    monkeypatch.setenv("CAVEMAN_PILOT", "rules")
    monkeypatch.setenv("CAVEMAN_PILOT_MIN_CHARS", "200")
    raw = "Attack with everything when ahead on board."
    result = compress_pilot_prompt(raw)
    assert result.applied is False
    assert result.text == raw


def test_compress_applies_to_long_notes(monkeypatch) -> None:
    """Long prompts are compressed and char count drops."""
    monkeypatch.setenv("CAVEMAN_PILOT", "rules")
    monkeypatch.setenv("CAVEMAN_PILOT_MIN_CHARS", "80")
    raw = (
        "You are piloting Ruby Storm, a Modern combo deck whose sole goal is "
        "to win by casting Grapeshot after assembling a storm count of 10 or "
        "more in a single turn.\n\n"
        "Resource priorities:\n"
        "  1. Land on turn 1 and 2 to reach 2 mana reliably.\n"
        "  2. Cost reducer on turn 2 or 3 -- this is the lynch-pin.\n"
    )
    result = compress_pilot_prompt(raw)
    assert result.applied is True
    assert result.compressed_chars < result.original_chars
    assert "Grapeshot" in result.text


def test_compress_off_passthrough(monkeypatch) -> None:
    """CAVEMAN_PILOT=off returns text unchanged."""
    monkeypatch.setenv("CAVEMAN_PILOT", "off")
    raw = "You are piloting a very verbose deck strategy note " * 5
    result = compress_pilot_prompt(raw)
    assert result.applied is False
    assert result.text == raw.strip()


def test_prompt_preview_truncates() -> None:
    """Preview helper caps long strings."""
    text = "x" * 1000
    preview = prompt_preview(text)
    assert len(preview) < len(text)
    assert preview.endswith("...")
