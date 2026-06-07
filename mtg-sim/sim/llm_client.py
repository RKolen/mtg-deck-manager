"""
LLM client for simulation pilots and statistics.

Prefers the host-side sidecar (SIDECAR_URL) so inference runs outside DDEV.
Falls back to direct Ollama (OLLAMA_URL) when the sidecar is not configured.
"""

from __future__ import annotations

import logging
import os

import requests
from ollama_http import (
    build_pilot_pick_prompt,
    generate_text as ollama_generate_text,
    is_configured as ollama_configured,
    parse_pilot_pick_index,
    pilot_pick_generate,
)

logger = logging.getLogger(__name__)

SIDECAR_URL: str = os.environ.get("SIDECAR_URL", "")


def is_configured() -> bool:
    """Return True when sidecar or direct Ollama is available."""
    return bool(SIDECAR_URL) or ollama_configured()


def llm_pick(
    question: str,
    option_names: list[str],
    state: dict,
    system_prompt: str = "",
) -> tuple[int, str]:
    """Ask the LLM to choose one option from a numbered list."""
    if not option_names:
        return 0, ""
    if SIDECAR_URL:
        return _sidecar_pick(question, option_names, state, system_prompt)
    if ollama_configured():
        prompt = build_pilot_pick_prompt(question, option_names, state, system_prompt)
        result = pilot_pick_generate(prompt)
        if not result.response and not result.thinking:
            return 0, ""
        index, reasoning = parse_pilot_pick_index(
            result.response, len(option_names), thinking=result.thinking,
            context={
                "question": question,
                "options": option_names,
                "state": state,
                "system_prompt": system_prompt,
            },
        )
        return index, reasoning
    return 0, ""


def generate_text(prompt: str, temperature: float = 0.2, max_tokens: int = 512) -> str:
    """Run an open-ended generation call.  Returns empty string on failure."""
    if SIDECAR_URL:
        return _sidecar_generate(prompt, temperature, max_tokens)
    return ollama_generate_text(prompt, temperature, max_tokens)


def _sidecar_pick(
    question: str,
    option_names: list[str],
    state: dict,
    system_prompt: str,
) -> tuple[int, str]:
    try:
        resp = requests.post(
            f"{SIDECAR_URL.rstrip('/')}/pilot-pick",
            json={
                "question": question,
                "options": option_names,
                "state": state,
                "system_prompt": system_prompt,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        index = int(data.get("index", 0))
        reasoning = str(data.get("reasoning", "")).strip()
        return max(0, min(len(option_names) - 1, index)), reasoning
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Sidecar pilot-pick failed: %s", exc)
        return 0, ""


def _sidecar_generate(prompt: str, temperature: float, max_tokens: int) -> str:
    try:
        resp = requests.post(
            f"{SIDECAR_URL.rstrip('/')}/generate",
            json={"prompt": prompt, "temperature": temperature, "max_tokens": max_tokens},
            timeout=60,
        )
        resp.raise_for_status()
        return str(resp.json().get("text", "")).strip()
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Sidecar generate failed: %s", exc)
        return ""
