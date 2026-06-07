"""Unit tests for Ollama pilot-pick parsing helpers."""

from __future__ import annotations

from ollama_http import (
    build_pilot_pick_prompt,
    extract_mulligan_rules,
    parse_pilot_pick_index,
    pilot_num_predict,
    think_enabled,
)


def test_build_attack_prompt_includes_board() -> None:
    """Combat picks include creature board state."""
    prompt = build_pilot_pick_prompt(
        "Choose ONE attack plan for this combat step.",
        ["Do not attack", "Attack with all (2 creatures)"],
        {
            "turn": 4,
            "own_life": 18,
            "opp_life": 15,
            "mana": 2,
            "own_creatures": "Satyr Hoplite (3/3), Monastery Swiftspear (1/2)",
            "opp_creatures": "",
            "legal_attackers": 2,
        },
        system_prompt="ATTACKING:\nAttack every turn with every creature.",
    )
    assert "Satyr Hoplite" in prompt
    assert "Opponent board: empty" in prompt
    assert "Attack rules:" in prompt


def test_mulligan_prompt_includes_factual_hand_stats() -> None:
    """Opening-hand picks report counts only; mulligan policy is in DECK STRATEGY."""
    prompt = build_pilot_pick_prompt(
        "Keep or mulligan this opening hand?",
        ["Keep", "Mulligan"],
        {
            "hand": "Mountain, Wooded Foothills, Temur Battle Rage",
            "hand_size": 3,
            "land_count": 2,
            "creature_count": 0,
        },
        system_prompt=(
            "Modern Hyper Heroic aggro deck.\n\n"
            "Mulligan rules:\n"
            "Ship any hand with zero creatures."
        ),
    )
    assert "Creatures in hand: 0" in prompt
    assert "Mulligan rules:" in prompt
    assert "Ship any hand with zero creatures" in prompt
    assert "MUST mulligan" not in prompt


def test_build_mulligan_prompt_includes_hand() -> None:
    """Opening-hand picks include card list and mulligan rules."""
    system = (
        "Pilot Ruby Storm.\n\n"
        "Mulligan rules:\n"
        "Keep 2-4 lands with reducer or ritual.\n"
        "Mulligan hands with no payoff by turn 3."
    )
    prompt = build_pilot_pick_prompt(
        "Keep or mulligan this opening hand?",
        ["Keep", "Mulligan"],
        {
            "hand": "Mountain, Ruby Medallion, Scalding Tarn, Opt, Opt, Bolt, Bolt",
            "hand_size": 7,
            "land_count": 2,
        },
        system_prompt=system,
    )
    assert "Mountain, Ruby Medallion" in prompt
    assert "2 lands" in prompt
    assert "Mulligan rules:" in prompt
    assert "Keep 2-4 lands" in prompt
    assert "Your entire reply must be ONE line containing ONLY 1 or 2." in prompt


def test_extract_mulligan_rules_from_heading() -> None:
    """Section heading mulligan rules are extracted for keep/mull prompts."""
    text = (
        "Deck identity: burn.\n\n"
        "Mulligan rules:\n"
        "Keep 2-5 lands with a one-drop.\n"
        "Ship hands with zero creatures.\n\n"
        "Combat rules:\n"
        "Attack with everything."
    )
    rules = extract_mulligan_rules(text)
    assert "Keep 2-5 lands" in rules
    assert "Ship hands" in rules
    assert "Combat rules" not in rules


def test_parse_from_final_line() -> None:
    """Last line-only number wins when thinking is enabled."""
    index, _ = parse_pilot_pick_index(
        "Let me think...\n\n2",
        3,
        thinking="Long reasoning here.",
    )
    assert index == 1


def test_parse_from_thinking_fallback() -> None:
    """When response is empty, parse the final digit from thinking."""
    index, reason = parse_pilot_pick_index("", 2, thinking="Best choice is 2.")
    assert index == 0
    assert reason == ""


def test_parse_from_thinking_final_line() -> None:
    """Thinking trace with final-line digit is parsed."""
    index, reason = parse_pilot_pick_index("", 3, thinking="Long analysis...\n2")
    assert index == 1
    assert reason == ""


def test_reasoning_strips_boilerplate() -> None:
    """Chain-of-thought openers are trimmed from pilot reasoning snippets."""
    _, reason = parse_pilot_pick_index(
        "2",
        2,
        thinking=(
            "First, I need to understand the deck strategy. "
            "Keep this hand because it has two lands and a creature."
        ),
    )
    assert reason == ""


def test_numeric_response_has_no_reasoning() -> None:
    """Pilot picks that return only a number omit log reasoning."""
    _, reason = parse_pilot_pick_index("2", 3, thinking="Long chain of thought...")
    assert reason == ""


def test_pilot_num_predict_no_think(monkeypatch) -> None:
    """Without thinking, pilot budget stays small."""
    monkeypatch.delenv("OLLAMA_PILOT_NUM_PREDICT", raising=False)
    monkeypatch.setenv("OLLAMA_THINK", "false")
    monkeypatch.setenv("OLLAMA_PILOT_RESPONSE_BUDGET", "64")
    assert pilot_num_predict() == 64


def test_pilot_num_predict_with_think(monkeypatch) -> None:
    """With thinking, budgets add into one num_predict total."""
    monkeypatch.delenv("OLLAMA_PILOT_NUM_PREDICT", raising=False)
    monkeypatch.setenv("OLLAMA_THINK", "true")
    monkeypatch.setenv("OLLAMA_PILOT_THINK_BUDGET", "512")
    monkeypatch.setenv("OLLAMA_PILOT_RESPONSE_BUDGET", "64")
    assert pilot_num_predict() == 576
    assert think_enabled() is True
