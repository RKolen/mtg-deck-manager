"""Caveman-style compression for MTG pilot prompts (field_notes, archetype priors).

Inspired by https://github.com/JuliusBrussee/caveman — strips filler and articles
while preserving card names, list structure, and strategic substance. Reduces tokens
sent to the sidecar on every pilot-pick call.
"""

from __future__ import annotations

import functools
import logging
import re
from dataclasses import dataclass

from env_loader import require_env, require_env_float, require_env_int
from ollama_http import generate_response_only, is_configured
from pilot_prompt_sanitize import is_contaminated_pilot_prompt

logger = logging.getLogger(__name__)

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_OFF = frozenset({"0", "false", "no", "off", ""})

_FILLER_WORDS = frozenset({
    "just", "really", "basically", "actually", "simply", "essentially",
    "generally", "surely", "certainly", "however", "furthermore",
    "additionally", "overall", "typically", "usually", "always", "never",
})

_PHRASE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bin order to\b", re.I), "to"),
    (re.compile(r"\bmake sure to\b", re.I), ""),
    (re.compile(r"\bthe reason is because\b", re.I), "because"),
    (re.compile(r"\byou are piloting\b", re.I), "Pilot"),
    (re.compile(r"\bwhose sole goal is to\b", re.I), "goal:"),
    (re.compile(r"\bin a single turn\b", re.I), "same turn"),
    (re.compile(r"\bdo not\b", re.I), "don't"),
    (re.compile(r"\bcan not\b", re.I), "can't"),
    (re.compile(r"\bwill not\b", re.I), "won't"),
    (re.compile(r"\bthere is no late game\b", re.I), "no late game"),
    (re.compile(r"\bthere's no late game\b", re.I), "no late game"),
    (
        re.compile(
            r"\bthe same race-or-lose logic applies every turn until the opponent dies\b",
            re.I,
        ),
        "race-or-lose every turn",
    ),
    (re.compile(r"\bthe deck's optimal kill is turn 3\b", re.I), "optimal T3 kill"),
    (re.compile(r"\bthe deck does not adapt or stabilize\b", re.I), "don't stabilize"),
    (re.compile(r"\bthe deck doesn't adapt or stabilize\b", re.I), "don't stabilize"),
    (re.compile(r"\bthe deck doesn't adapt\b", re.I), "don't adapt"),
    (re.compile(r"\bevery decision must\b", re.I), "decide:"),
    (re.compile(r"\bapply the rules identically\b", re.I), "same rules every turn"),
    (re.compile(r"\s+--\s+", re.I), "; "),
)

_ARTICLE_BEFORE_LOWER = re.compile(r"\b(a|an|the)\s+(?=[a-z])", re.I)
_MULTI_SPACE = re.compile(r" {2,}")
_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class CompressedPrompt:
    """Result of compressing one pilot prompt string."""

    text: str
    original_chars: int
    compressed_chars: int
    mode: str
    applied: bool


def _env_mode() -> str:
    """Return compression mode: off, rules, or llm."""
    raw = require_env("CAVEMAN_PILOT").lower()
    if raw in _OFF:
        return "off"
    if raw in ("llm", "ollama", "model"):
        return "llm"
    return "rules"


def _min_chars() -> int:
    return require_env_int("CAVEMAN_PILOT_MIN_CHARS")


def _meaningful_compression(original_chars: int, compressed_chars: int) -> bool:
    """Return True when compression saved enough to report as applied."""
    if compressed_chars >= original_chars:
        return False
    saved = original_chars - compressed_chars
    ratio = saved / original_chars if original_chars else 0.0
    min_saved = require_env_int("CAVEMAN_PILOT_MIN_SAVED")
    min_ratio = require_env_float("CAVEMAN_PILOT_MIN_RATIO")
    return saved >= min_saved or ratio >= min_ratio


def _preview_max() -> int:
    return require_env_int("CAVEMAN_PILOT_PREVIEW_CHARS")


def _compress_prose_line(line: str) -> str:
    """Compress one line of natural-language pilot text."""
    text = line.strip()
    if not text:
        return ""
    for pattern, repl in _PHRASE_REPLACEMENTS:
        text = pattern.sub(repl, text)
    words = text.split()
    kept: list[str] = []
    for word in words:
        bare = word.strip(".,;:!?\"'()[]")
        lower = bare.lower()
        if lower in _FILLER_WORDS:
            continue
        kept.append(word)
    text = " ".join(kept)
    text = _ARTICLE_BEFORE_LOWER.sub("", text)
    text = _MULTI_SPACE.sub(" ", text).strip()
    return text


def _compress_line(line: str) -> str:
    """Compress one line while preserving list/heading structure."""
    if not line.strip():
        return ""
    heading = re.match(r"^(\s*)([A-Za-z][^:\n]{0,80}:)\s*$", line)
    if heading:
        body = _compress_prose_line(heading.group(2).rstrip(":"))
        return f"{heading.group(1)}{body}:"
    bullet = re.match(r"^(\s*[-*+]\s+)(.*)$", line)
    if bullet:
        return f"{bullet.group(1)}{_compress_prose_line(bullet.group(2))}"
    numbered = re.match(r"^(\s*\d+\.\s+)(.*)$", line)
    if numbered:
        return f"{numbered.group(1)}{_compress_prose_line(numbered.group(2))}"
    return _compress_prose_line(line)


def _dedupe_paragraphs(text: str) -> str:
    """Drop duplicate paragraphs while preserving order."""
    seen: set[str] = set()
    kept: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        stripped = block.strip()
        if not stripped:
            continue
        key = re.sub(r"\s+", " ", stripped.lower())[:120]
        if key in seen:
            continue
        seen.add(key)
        kept.append(stripped)
    return "\n\n".join(kept)


def compress_pilot_prompt_rules(text: str) -> str:
    """Deterministic caveman compression (no API calls)."""
    if not text.strip():
        return ""
    lines = [_compress_line(line) for line in text.splitlines()]
    joined = "\n".join(line for line in lines if line is not None)
    joined = _dedupe_paragraphs(joined)
    joined = _BLANK_LINES.sub("\n\n", joined).strip()
    return joined


def _build_llm_compress_prompt(original: str) -> str:
    return (
        "Compress this MTG deck pilot strategy into caveman format.\n\n"
        "STRICT RULES:\n"
        "- Preserve ALL card names, archetype names, and mana costs exactly\n"
        "- Preserve numbered/bulleted list structure and section headings\n"
        "- Drop articles, filler, hedging, pleasantries\n"
        "- Short synonyms OK. Fragments OK.\n"
        "- Return ONLY compressed text — no outer markdown fence\n\n"
        f"TEXT:\n{original}"
    )


def compress_pilot_prompt_llm(text: str) -> str:
    """Compress via Ollama when configured; fall back to rules on failure."""
    if not is_configured():
        logger.warning("CAVEMAN_PILOT=llm but Ollama not configured; using rules")
        return compress_pilot_prompt_rules(text)
    max_tokens = max(256, min(2048, len(text)))
    compressed = generate_response_only(
        _build_llm_compress_prompt(text),
        temperature=0.1,
        max_tokens=max_tokens,
    ).strip()
    if not compressed or is_contaminated_pilot_prompt(compressed):
        logger.warning("Caveman LLM compression invalid; using rules")
        return compress_pilot_prompt_rules(text)
    if compressed.strip() == text.strip():
        logger.warning("Caveman LLM compression unchanged; using rules")
        return compress_pilot_prompt_rules(text)
    return compressed


def finalize_pilot_prompt(raw: str, compressed: CompressedPrompt) -> CompressedPrompt:
    """Return a clean pilot prompt, falling back to rules if LLM output is poisoned."""
    if not raw.strip():
        return compressed
    if not is_contaminated_pilot_prompt(compressed.text):
        return compressed
    logger.error(
        "Pilot prompt failed contamination check (%d chars); using rules compression",
        len(compressed.text),
    )
    rules_text = compress_pilot_prompt_rules(raw)
    return CompressedPrompt(
        text=rules_text,
        original_chars=len(raw),
        compressed_chars=len(rules_text),
        mode="rules",
        applied=_meaningful_compression(len(raw), len(rules_text)),
    )


@functools.lru_cache(maxsize=64)
def _compress_cached(text: str, mode: str) -> CompressedPrompt:
    """Cache compression by text+mode within the sim process."""
    original_chars = len(text)
    if mode == "llm":
        compressed = compress_pilot_prompt_llm(text)
    else:
        compressed = compress_pilot_prompt_rules(text)
    return CompressedPrompt(
        text=compressed,
        original_chars=original_chars,
        compressed_chars=len(compressed),
        mode=mode,
        applied=_meaningful_compression(original_chars, len(compressed)),
    )


def compress_pilot_prompt(text: str) -> CompressedPrompt:
    """Compress a pilot prompt when CAVEMAN_PILOT is enabled."""
    stripped = text.strip()
    if not stripped:
        return CompressedPrompt("", 0, 0, "off", False)
    mode = _env_mode()
    if mode == "off" or len(stripped) < _min_chars():
        return CompressedPrompt(
            stripped,
            len(stripped),
            len(stripped),
            mode,
            False,
        )
    result = _compress_cached(stripped, mode)
    finalized = finalize_pilot_prompt(stripped, result)
    if finalized.original_chars and finalized.compressed_chars < finalized.original_chars:
        logger.info(
            "Caveman pilot compress (%s): %d -> %d chars (%.0f%%)",
            finalized.mode,
            finalized.original_chars,
            finalized.compressed_chars,
            100 * (1 - finalized.compressed_chars / finalized.original_chars),
        )
    return finalized


def prompt_preview(text: str) -> str:
    """Return a truncated preview of a prompt for API/UI display."""
    if not text:
        return ""
    limit = _preview_max()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
