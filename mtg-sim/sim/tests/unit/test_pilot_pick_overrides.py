"""Unit tests for prompt-only pilot picks (no deck-specific overrides)."""

from __future__ import annotations

from forge_verbose_parser import _parse_forge_verbose_output
from ollama_http import build_pilot_pick_prompt, parse_pilot_pick_index
from pilot_prompt_sanitize import extract_spell_rules


def test_spell_prompt_includes_hand_and_storm_context() -> None:
    """Spell picks surface board/hand/storm facts; strategy comes from system prompt."""
    prompt = build_pilot_pick_prompt(
        "Choose the ONE spell to cast from the legal options.",
        ["Grapeshot (Sorcery, CMC 2)", "Desperate Ritual (Instant, CMC 2)"],
        {
            "turn": 5,
            "own_life": 18,
            "opp_life": 14,
            "hand_size": 4,
            "hand_cards": "Grapeshot, Desperate Ritual, Ruby Medallion, Mountain",
            "storm_count": 3,
            "pilot_mode": "combo",
            "lands_in_play": 2,
            "board_creatures": 0,
        },
        system_prompt=(
            "Ruby Storm combo.\n\n"
            "Spell priority:\n"
            "Never cast Grapeshot until storm count is lethal.\n"
        ),
    )
    assert "Hand: Grapeshot, Desperate Ritual" in prompt
    assert "Storm count this turn: 3" in prompt
    assert "Spell casting rules:" in prompt
    assert "Never cast Grapeshot until storm count is lethal" in prompt
    assert "Temur Battle Rage" not in prompt
    assert "Follow DECK STRATEGY above" in prompt


def test_extract_spell_rules_from_heading() -> None:
    """Spell sections are extracted from field_notes-style prompts."""
    text = (
        "Deck identity: combo.\n\n"
        "Spell priority:\n"
        "Cast rituals before Grapeshot.\n"
        "Ship Grapeshot on turn 1.\n\n"
        "Mulligan rules:\n"
        "Keep reducers."
    )
    rules = extract_spell_rules(text)
    assert "Cast rituals before Grapeshot" in rules
    assert "Mulligan" not in rules


def test_parse_board_from_pilot_attack() -> None:
    """Board development stats use pilot attack lines keyed by turn number."""
    stdout = "\n".join([
        "Turn: Turn 2 (Ai(1)-Heroic)",
        "[Pilot] Ai(1)-Heroic: T2 spell: Monastery Swiftspear",
        "[Pilot] Ai(1)-Heroic: T2 attack: Attack with all (1 creatures)",
        "Turn: Turn 4 (Ai(1)-Heroic)",
        "[Pilot] Ai(1)-Heroic: T9 attack: Attack with all (3 creatures)",
        "[Pilot] Ai(1)-Heroic: T4 attack: Attack with all (2 creatures)",
        "Game Result: Game 1 ended in 100 ms. Ai(1)-Heroic has won!",
    ])
    results = _parse_forge_verbose_output(stdout, "Heroic")
    turns = results[0].log.turns if results[0].log else []
    t2 = next(ev for ev in turns if ev.turn == 2 and ev.player == 0)
    t4 = next(ev for ev in turns if ev.turn == 4 and ev.player == 0)
    assert t2.creatures_in_play == 1
    assert t4.creatures_in_play == 2


def test_unparseable_pick_defaults_to_first_option() -> None:
    """When the model returns no number, pick option 1 (no strategy override)."""
    index, reason = parse_pilot_pick_index("I think land is best.", 3)
    assert index == 0
    assert reason == ""
