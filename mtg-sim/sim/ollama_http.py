"""Shared Ollama HTTP helpers for the sim service and host sidecar."""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "")


def is_configured() -> bool:
    """Return True when Ollama URL and model are set."""
    return bool(OLLAMA_URL and OLLAMA_MODEL)


def build_pilot_pick_prompt(
    question: str,
    options: list[str],
    state: dict,
    system_prompt: str = "",
) -> str:
    """Build the full prompt for a numbered pilot-pick decision."""
    turn = state.get("turn", 1)
    own_life = state.get("own_life", 20)
    opp_life = state.get("opp_life", 20)
    mana = state.get("mana", 0)
    numbered = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(options))
    context = (
        f"Turn {turn}.  Your life: {own_life}.  "
        f"Opponent life: {opp_life}.  Available mana: {mana}."
    )
    body = (
        f"{question}\n\n"
        f"{context}\n\n"
        f"Options:\n{numbered}\n\n"
        "Reply with ONLY the number of the best option (e.g. 2)."
    )
    return f"{system_prompt}\n\n{body}" if system_prompt else body


def generate_text(prompt: str, temperature: float = 0.2, max_tokens: int = 512) -> str:
    """Call Ollama /api/generate and return the response text."""
    if not is_configured():
        return ""
    try:
        resp = requests.post(
            f"{OLLAMA_URL.rstrip('/')}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=60,
        )
        resp.raise_for_status()
        return str(resp.json().get("response", "")).strip()
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Ollama generate failed: %s", exc)
        return ""


def parse_pilot_pick_index(text: str, option_count: int) -> tuple[int, str]:
    """Parse a 1-based option number from model output."""
    if not text:
        return 0, ""
    try:
        choice = int(text.split()[0]) - 1
    except (ValueError, IndexError):
        choice = 0
    return max(0, min(option_count - 1, choice)), text
