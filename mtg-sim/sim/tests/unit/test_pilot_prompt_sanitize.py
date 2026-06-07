"""Unit tests for pilot prompt contamination detection."""

from __future__ import annotations

from caveman_compress import finalize_pilot_prompt, CompressedPrompt
from ollama_http import parse_pilot_pick_index
from pilot_prompt_sanitize import extract_attack_rules, is_contaminated_pilot_prompt


def test_detects_caveman_chain_of_thought() -> None:
    """Compression meta-text is flagged as contaminated."""
    poison = (
        "We are compressing the given MTG deck pilot strategy into caveman format. "
        "STRICT RULES: preserve numbered/bulleted list structure."
    )
    assert is_contaminated_pilot_prompt(poison) is True


def test_clean_strategy_not_contaminated() -> None:
    """Normal deck strategy text passes the contamination check."""
    clean = (
        "Modern Hyper Heroic burn. Optimal T3 kill; race-or-lose every turn.\n\n"
        "ATTACKING:\n"
        "- Attack every turn with every creature.\n"
    )
    assert is_contaminated_pilot_prompt(clean) is False


def test_finalize_pilot_prompt_falls_back_to_rules() -> None:
    """Poisoned LLM compression is replaced with rules compression."""
    raw = (
        "You are piloting a deck that basically just wants to attack with "
        "the biggest creature on the board every single turn."
    )
    poisoned = CompressedPrompt(
        text="We are compressing the MTG deck pilot strategy into caveman format.",
        original_chars=len(raw),
        compressed_chars=70,
        mode="llm",
        applied=True,
    )
    result = finalize_pilot_prompt(raw, poisoned)
    assert result.mode == "rules"
    assert "basically" not in result.text.lower()
    assert is_contaminated_pilot_prompt(result.text) is False


def test_unparseable_attack_defaults_to_first_option() -> None:
    """Unparseable picks default to option 1; no deck-specific fallback."""
    options = [
        "Do not attack",
        "Attack with all (2 creatures)",
        "Attack with Hoplite only",
    ]
    index, reason = parse_pilot_pick_index(
        "",
        len(options),
        thinking="We are compressing the MTG deck pilot strategy into caveman format.",
        context={
            "question": "Choose ONE attack plan for this combat step.",
            "options": options,
            "state": {},
        },
    )
    assert index == 0
    assert reason == ""


def test_extract_attack_rules_from_heading() -> None:
    """Attack section is extracted for combat pilot picks."""
    text = (
        "Win on turn 3.\n\n"
        "ATTACKING:\n"
        "Attack every turn with every creature.\n"
        "NEVER hold back for next turn.\n\n"
        "Mulligan rules:\n"
        "Keep 2-4 lands with a one-drop."
    )
    rules = extract_attack_rules(text)
    assert "Attack every turn" in rules
    assert "Mulligan" not in rules
