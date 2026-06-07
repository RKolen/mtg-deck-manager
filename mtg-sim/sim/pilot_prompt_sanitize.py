"""Detect and recover from poisoned LLM pilot strategy prompts."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_CONTAMINATION_MARKERS: tuple[str, ...] = (
    "compress this mtg deck pilot strategy",
    "compress the mtg deck pilot strategy",
    "compress the given mtg deck pilot strategy",
    "into caveman format",
    "into \"caveman\" format",
    "we are compressing the given",
    "we are compressing the mtg",
    "preserve numbered/bulleted list structure",
    "strict rules:",
    "choose the one spell to cast from the legal options",
    "steps: 1. read the text",
)

_ATTACK_SECTION = re.compile(
    r"(?i)^(?:#+\s*|\*\*)?(?:attacking|attack rules|attack is the default)(?:\*\*)?\s*:?\s*$",
)
_SPELL_SECTION = re.compile(
    r"(?i)^(?:#+\s*|\*\*)?"
    r"(?:spell(?:\s+priority|\s+rules|\s+casting)?|casting(?:\s+order|\s+priority)?|"
    r"combo(?:\s+line|\s+turn)?|lethal(?:\s+line)?)"
    r"(?:\*\*)?\s*:?\s*$",
)
_MULLIGAN_SECTION = re.compile(
    r"(?i)^(?:#+\s*|\*\*)?(?:opening\s+)?mulligan(?:\s+rules)?(?:\*\*)?\s*:?\s*$",
)
_SECTION_BREAK = re.compile(r"^[A-Z][A-Za-z /'-]{2,40}:$")


def is_contaminated_pilot_prompt(text: str) -> bool:
    """Return True when text looks like caveman-compress chain-of-thought, not strategy."""
    if not text.strip():
        return False
    sample = text[:1500].lower()
    hits = sum(1 for marker in _CONTAMINATION_MARKERS if marker in sample)
    if hits >= 2:
        return True
    if hits == 1 and ("caveman" in sample or "compress" in sample):
        return True
    return False


def _extract_section(text: str, heading: re.Pattern[str], max_chars: int) -> str:
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if heading.match(line.strip()):
            start = index + 1
            break
    if start is None:
        return ""
    section: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped and _SECTION_BREAK.match(stripped):
            break
        if stripped:
            section.append(line.rstrip())
    return "\n".join(section).strip()[:max_chars]


def extract_attack_rules(system_prompt: str, max_chars: int = 700) -> str:
    """Pull attack/combat rules from a pilot strategy prompt."""
    if not system_prompt.strip():
        return ""
    section = _extract_section(system_prompt, _ATTACK_SECTION, max_chars)
    if section:
        return section
    hits = [
        line.rstrip()
        for line in system_prompt.splitlines()
        if re.search(r"(?i)attack (every|with all|is the default)", line)
    ][:8]
    return "\n".join(hits).strip()[:max_chars]


def extract_spell_rules(system_prompt: str, max_chars: int = 700) -> str:
    """Pull spell-casting / combo rules from a pilot strategy prompt."""
    if not system_prompt.strip():
        return ""
    section = _extract_section(system_prompt, _SPELL_SECTION, max_chars)
    if section:
        return section
    hits = [
        line.rstrip()
        for line in system_prompt.splitlines()
        if re.search(
            r"(?i)(cast|storm count|grapeshot|pump|lethal|priorit|combo turn)",
            line,
        )
    ][:10]
    return "\n".join(hits).strip()[:max_chars]


def extract_mulligan_rules_from_strategy(system_prompt: str, max_chars: int = 800) -> str:
    """Pull mulligan rules from a pilot strategy prompt."""
    if not system_prompt.strip():
        return ""
    section = _extract_section(system_prompt, _MULLIGAN_SECTION, max_chars)
    if section:
        return section
    hits = [
        line.rstrip()
        for line in system_prompt.splitlines()
        if re.search(r"(?i)mulligan", line)
    ][:10]
    return "\n".join(hits).strip()[:max_chars]
