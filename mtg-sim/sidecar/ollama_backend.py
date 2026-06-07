"""Ollama backend for the host-side sidecar."""

from __future__ import annotations

from ollama_http import (
    OLLAMA_MODEL,
    build_pilot_pick_prompt,
    generate_text,
    is_configured,
    parse_pilot_pick_index,
    pilot_pick_generate,
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
    result = pilot_pick_generate(prompt)
    if not result.response and not result.thinking:
        raise RuntimeError("Ollama returned an empty pilot-pick response")
    index, reasoning = parse_pilot_pick_index(
        result.response,
        len(options),
        thinking=result.thinking,
        context={
            "question": question,
            "options": options,
            "state": state,
            "system_prompt": system_prompt,
        },
    )
    return index, reasoning
