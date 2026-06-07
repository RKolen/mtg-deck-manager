"""Shared Ollama HTTP helpers for the sim service and host sidecar."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import requests

from pilot_prompt_sanitize import (
    extract_attack_rules,
    extract_mulligan_rules_from_strategy,
    extract_spell_rules,
    is_contaminated_pilot_prompt,
)

logger = logging.getLogger(__name__)

OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "")

_TRUTHY = frozenset({"1", "true", "yes", "on"})

_ANSWER_MULL = (
    "Follow the mulligan rules from DECK STRATEGY above. "
    "Your entire reply must be ONE line containing ONLY 1 or 2."
)
_ANSWER_PICK = (
    "Follow DECK STRATEGY above. "
    "Your entire reply must be ONE line containing ONLY the option number."
)


@dataclass(frozen=True)
class OllamaGenerateResult:
    """Parsed body from a non-streaming Ollama /api/generate call."""

    response: str
    thinking: str


def is_configured() -> bool:
    """Return True when Ollama URL and model are set."""
    return bool(OLLAMA_URL and OLLAMA_MODEL)


def think_enabled() -> bool:
    """Return True when Ollama thinking mode is enabled via OLLAMA_THINK."""
    return os.environ.get("OLLAMA_THINK", "false").strip().lower() in _TRUTHY


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def pilot_num_predict() -> int:
    """Total num_predict for pilot-pick calls."""
    override = os.environ.get("OLLAMA_PILOT_NUM_PREDICT", "").strip()
    if override:
        return int(override)
    response_budget = _env_int("OLLAMA_PILOT_RESPONSE_BUDGET", 64)
    if not think_enabled():
        return max(response_budget, 32)
    think_budget = _env_int("OLLAMA_PILOT_THINK_BUDGET", 512)
    return think_budget + response_budget


def generate_num_predict(max_tokens: int) -> int:
    """Total num_predict for open-ended generate calls."""
    override = os.environ.get("OLLAMA_GENERATE_NUM_PREDICT", "").strip()
    if override:
        return int(override)
    if think_enabled():
        think_budget = _env_int("OLLAMA_GENERATE_THINK_BUDGET", 1024)
        return think_budget + max(max_tokens, 128)
    return max_tokens


def extract_mulligan_rules(system_prompt: str, max_chars: int = 800) -> str:
    """Pull the mulligan-rules section from a long pilot strategy prompt."""
    return extract_mulligan_rules_from_strategy(system_prompt, max_chars)


def _sanitize_system_prompt(system_prompt: str) -> str:
    """Drop poisoned caveman-compress output from the strategy block."""
    stripped = system_prompt.strip()
    if not stripped:
        return ""
    if is_contaminated_pilot_prompt(stripped):
        logger.warning("Ignoring contaminated pilot system prompt (%d chars)", len(stripped))
        return ""
    return stripped


def _append_hand_summary(parts: list[str], state: dict) -> None:
    """Add hand size and card names when Forge sends them."""
    hand_size = state.get("hand_size")
    if hand_size is not None:
        parts.append(f"Cards in hand: {hand_size}.")
    hand_cards = state.get("hand_cards")
    if hand_cards:
        parts.append(f"Hand: {hand_cards}.")


def _format_hand_context(state: dict) -> str:
    """Format opening-hand context for mulligan decisions."""
    hand_raw = state.get("hand", "")
    if isinstance(hand_raw, list):
        hand_text = ", ".join(str(card) for card in hand_raw)
    else:
        hand_text = str(hand_raw)
    hand_size = state.get("hand_size", "?")
    land_count = state.get("land_count", "?")
    parts = [f"Hand ({hand_size} cards, {land_count} lands): {hand_text}."]
    creature_count = state.get("creature_count")
    if creature_count is not None:
        parts.append(f"Creatures in hand: {creature_count}.")
        one_drops = state.get("one_drop_count")
        if one_drops is not None:
            parts.append(f"One-drop creatures: {one_drops}.")
    cards_to_bottom = state.get("cards_to_bottom")
    if cards_to_bottom:
        parts.append(f"London mulligan: bottom {cards_to_bottom} if you keep.")
    bottom_remaining = state.get("cards_to_bottom_remaining")
    if bottom_remaining:
        total = state.get("cards_to_bottom_total", bottom_remaining)
        parts.append(
            f"Bottom step: put {bottom_remaining} of {total} card(s) on bottom."
        )
    deck_name = state.get("deck_name")
    if deck_name:
        parts.append(f"Deck: {deck_name}.")
    return " ".join(parts)


def _format_combat_context(state: dict) -> str:
    """Format board state for attack-plan decisions."""
    turn = state.get("turn", 1)
    own_life = state.get("own_life", 20)
    opp_life = state.get("opp_life", 20)
    mana = state.get("mana", 0)
    parts = [
        f"Turn {turn}. Your life: {own_life}. Opponent life: {opp_life}. "
        f"Available mana: {mana}.",
    ]
    own_creatures = state.get("own_creatures")
    if own_creatures:
        parts.append(f"Your board: {own_creatures}.")
    opp_creatures = state.get("opp_creatures")
    if opp_creatures:
        parts.append(f"Opponent board: {opp_creatures}.")
    else:
        parts.append("Opponent board: empty.")
    legal_attackers = state.get("legal_attackers")
    if legal_attackers is not None:
        parts.append(f"Legal attackers: {legal_attackers}.")
    board_power = state.get("board_power")
    if board_power is not None:
        parts.append(f"Board power: {board_power}.")
    _append_hand_summary(parts, state)
    return " ".join(parts)


def _format_block_context(state: dict) -> str:
    """Format board state for blocking decisions."""
    turn = state.get("turn", 1)
    own_life = state.get("own_life", 20)
    parts = [
        f"Turn {turn}. Your life: {own_life}.",
        f"Attacker: {state.get('attacker', '?')} "
        f"({state.get('attacker_power', '?')}/{state.get('attacker_toughness', '?')}).",
    ]
    blockers = state.get("legal_blockers")
    if blockers:
        parts.append(f"Legal blockers: {blockers}.")
    return " ".join(parts)


def _format_turn_context(state: dict) -> str:
    """Format generic in-game turn context."""
    turn = state.get("turn", 1)
    own_life = state.get("own_life", 20)
    opp_life = state.get("opp_life", 20)
    mana = state.get("mana", 0)
    return (
        f"Turn {turn}.  Your life: {own_life}.  "
        f"Opponent life: {opp_life}.  Available mana: {mana}."
    )


def _format_spell_context(state: dict) -> str:
    """Format spell-choice context (Forge LlmPilotSpellSupport state)."""
    parts = [_format_turn_context(state)]
    _append_hand_summary(parts, state)
    lands = state.get("lands_in_play")
    if lands is not None:
        parts.append(f"Lands in play: {lands}.")
    board_creatures = state.get("board_creatures")
    if board_creatures is not None:
        parts.append(f"Creatures in play: {board_creatures}.")
    own_creatures = state.get("own_creatures")
    if own_creatures:
        parts.append(f"Your board: {own_creatures}.")
    board_power = state.get("board_power")
    if board_power is not None:
        parts.append(f"Board power: {board_power}.")
    if "storm_count" in state:
        parts.append(f"Storm count this turn: {state.get('storm_count', 0)}.")
    pilot_mode = state.get("pilot_mode")
    if pilot_mode:
        parts.append(f"Pilot mode: {pilot_mode}.")
    return " ".join(parts)


def _format_pilot_context(state: dict) -> str:
    """Build decision context for mulligan vs in-game pilot picks."""
    if "hand" in state:
        return _format_hand_context(state)
    if "own_creatures" in state or "legal_attackers" in state:
        return _format_combat_context(state)
    if "attacker" in state:
        return _format_block_context(state)
    if "storm_count" in state or "lands_in_play" in state:
        return _format_spell_context(state)
    return _format_turn_context(state)


def _pilot_answer_rule(question_lower: str, is_keep_or_mull: bool) -> str:
    """Generic answer-format instruction; strategy lives in DECK STRATEGY only."""
    if is_keep_or_mull:
        return _ANSWER_MULL
    return _ANSWER_PICK


def build_pilot_pick_prompt(
    question: str,
    options: list[str],
    state: dict,
    system_prompt: str = "",
) -> str:
    """Build the full prompt for a numbered pilot-pick decision."""
    strategy = _sanitize_system_prompt(system_prompt)
    numbered = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(options))
    context = _format_pilot_context(state)
    question_lower = question.lower()
    is_keep_or_mull = (
        "hand" in state
        and len(options) == 2
        and {opt.lower() for opt in options} == {"keep", "mulligan"}
    )
    answer_rule = _pilot_answer_rule(question_lower, is_keep_or_mull)
    is_attack_pick = "attack plan" in question_lower
    is_spell_pick = "spell to cast" in question_lower

    body_parts: list[str] = [question, "", context]
    if is_keep_or_mull:
        rules = extract_mulligan_rules(strategy)
        if rules:
            body_parts.extend(["", "Mulligan rules:", rules])
    if is_attack_pick:
        rules = extract_attack_rules(strategy)
        if rules:
            body_parts.extend(["", "Attack rules:", rules])
    if is_spell_pick:
        rules = extract_spell_rules(strategy)
        if rules:
            body_parts.extend(["", "Spell casting rules:", rules])
    body_parts.extend(["", f"Options:\n{numbered}", "", answer_rule])
    body = "\n".join(body_parts)
    if strategy:
        return f"DECK STRATEGY (follow exactly):\n{strategy}\n\n---\n\n{body}"
    return body


def _ollama_num_ctx() -> int | None:
    """Return OLLAMA_NUM_CTX env value, or None to let Ollama use its default."""
    raw = os.environ.get("OLLAMA_NUM_CTX", "").strip()
    if not raw:
        return None
    return int(raw)


def _ollama_post(payload: dict[str, Any]) -> OllamaGenerateResult:
    """POST to Ollama /api/generate and parse thinking vs response fields."""
    num_ctx = _ollama_num_ctx()
    if num_ctx is not None:
        payload.setdefault("options", {})["num_ctx"] = num_ctx
    resp = requests.post(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return OllamaGenerateResult(
        response=str(data.get("response", "")).strip(),
        thinking=str(data.get("thinking", "")).strip(),
    )


def ollama_generate(
    prompt: str,
    *,
    temperature: float,
    num_predict: int,
    use_think: bool | None = None,
) -> OllamaGenerateResult:
    """Call Ollama /api/generate; when thinking is on, both fields may be filled."""
    if not is_configured():
        return OllamaGenerateResult(response="", thinking="")
    think = think_enabled() if use_think is None else use_think
    try:
        return _ollama_post({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": think,
            "options": {"temperature": temperature, "num_predict": num_predict},
        })
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Ollama generate failed: %s", exc)
        return OllamaGenerateResult(response="", thinking="")


def generate_response_only(
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> str:
    """Call Ollama and return response text only (never chain-of-thought thinking)."""
    result = ollama_generate(
        prompt,
        temperature=temperature,
        num_predict=generate_num_predict(max_tokens),
        use_think=False,
    )
    return result.response.strip()


def generate_text(prompt: str, temperature: float = 0.2, max_tokens: int = 512) -> str:
    """Call Ollama /api/generate and return the best available answer text."""
    result = ollama_generate(
        prompt,
        temperature=temperature,
        num_predict=generate_num_predict(max_tokens),
    )
    if result.response.strip():
        return result.response.strip()
    return result.thinking.strip()


def pilot_pick_generate(prompt: str) -> OllamaGenerateResult:
    """Run a pilot-pick generation; always disables thinking (number-only output)."""
    return ollama_generate(
        prompt,
        temperature=0.1,
        num_predict=max(_env_int("OLLAMA_PILOT_RESPONSE_BUDGET", 64), 32),
        use_think=False,
    )


def _index_from_text(text: str, option_count: int) -> int | None:
    """Extract a 0-based option index from the model's final answer line only."""
    if not text or option_count <= 0:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    last = lines[-1]
    if re.fullmatch(r"\d+", last):
        index = int(last) - 1
        if 0 <= index < option_count:
            return index
    labeled = re.search(r"(?:answer|option|choice)\s*:?\s*(\d+)\s*$", last, re.I)
    if labeled:
        index = int(labeled.group(1)) - 1
        if 0 <= index < option_count:
            return index
    return None


def parse_pilot_pick_index(
    response: str,
    option_count: int,
    thinking: str = "",
    *,
    context: dict | None = None,
) -> tuple[int, str]:
    """Parse a 1-based option number from the model's final answer line."""
    for text in (response, thinking):
        if is_contaminated_pilot_prompt(text):
            continue
        raw_index = _index_from_text(text, option_count)
        if raw_index is not None:
            index = max(0, min(option_count - 1, raw_index))
            return index, ""
    logger.warning(
        "Unparseable pilot pick; defaulting to option 1 (context keys: %s)",
        sorted((context or {}).get("state", {}).keys()),
    )
    return 0, ""
