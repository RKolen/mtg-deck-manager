"""Ollama backend for the host-side sidecar."""

from __future__ import annotations

from ollama_http import (
    OLLAMA_MODEL,
    build_pilot_pick_prompt,
    generate_text,
    is_configured,
    parse_pilot_pick_index,
)

__all__ = ["OLLAMA_MODEL", "generate_text", "is_configured", "pilot_pick"]


def pilot_pick(
    question: str,
    options: list[str],
    state: dict,
    system_prompt: str = "",
) -> tuple[int, str]:
    """Ask Ollama to choose one option from a numbered list."""
    prompt = build_pilot_pick_prompt(question, options, state, system_prompt)
    text = generate_text(prompt, temperature=0.1, max_tokens=150)
    if not text:
        raise RuntimeError("Ollama returned an empty pilot-pick response")
    return parse_pilot_pick_index(text, len(options))
