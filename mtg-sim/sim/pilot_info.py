"""Engine selection and pilot-debug metadata for simulation runs."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from caveman_compress import CompressedPrompt, prompt_preview
from pilot_prompts import get_pilot_prompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineRequest:
    """Inputs used to log which Forge pilots will run."""

    llm_ready: bool
    opponent_archetype: str
    opp_drupal_prompt: str
    player_prompt: str


def _pilot_source(archetype: str, drupal_prompt: str, resolved: str) -> str:
    """Return where the effective opponent pilot prompt came from."""
    if not resolved:
        return "none"
    if drupal_prompt.strip():
        return "drupal"
    if get_pilot_prompt(archetype, ""):
        return "builtin"
    return "generic"


def resolve_sim_engine(req: EngineRequest) -> str:
    """Log sidecar/pilot availability and return ``forge``."""
    opp_resolved = get_pilot_prompt(req.opponent_archetype, req.opp_drupal_prompt)
    player_resolved = req.player_prompt.strip()

    if req.llm_ready and (opp_resolved or player_resolved):
        logger.info(
            "engine: forge + LLM sidecar (opp=%d chars, player=%d chars)",
            len(opp_resolved),
            len(player_resolved),
        )
    else:
        logger.info("engine: forge (built-in AI; sidecar or prompts unavailable)")
    return "forge"


@dataclass(frozen=True)
class PilotInfoRequest:
    """Inputs for building simulation pilot metadata."""

    opponent_archetype: str
    opp_drupal_prompt: str
    player: CompressedPrompt
    opponent: CompressedPrompt
    llm_ready: bool


def build_pilot_info(req: PilotInfoRequest) -> dict:
    """Build API metadata explaining which AI piloted each side."""
    player_resolved = req.player.text
    opp_resolved = req.opponent.text
    opp_source = _pilot_source(
        req.opponent_archetype, req.opp_drupal_prompt, opp_resolved,
    )
    caveman_mode = req.player.mode if req.player.mode != "off" else req.opponent.mode

    opp_active = req.llm_ready and bool(opp_resolved)
    player_active = req.llm_ready and bool(player_resolved)
    if opp_active and player_active:
        message = (
            "Forge + LLM sidecar: your deck (field_notes) and selected archetype "
            f"({opp_source}) both use LLM pilots; Forge handles rules and mana."
        )
    elif opp_active:
        message = (
            f"Forge + LLM sidecar: selected archetype ({opp_source}) uses an LLM "
            "pilot; Forge handles rules and mana."
        )
    elif player_active:
        message = (
            "Forge + LLM sidecar: your deck field_notes use an LLM pilot; "
            "Forge handles rules and mana."
        )
    elif req.llm_ready and (opp_resolved or player_resolved):
        message = (
            "Forge: pilot prompt loaded but sidecar unavailable; "
            "built-in AI used for both sides."
        )
    else:
        message = (
            "Forge engine: built-in AI for both sides "
            "(set SIDECAR_URL and pilot prompts for LLM pilots)."
        )
    return {
        "engineUsed": "forge",
        "opponentPilotActive": opp_active,
        "playerPilotActive": player_active,
        "opponentPilotSource": opp_source if opp_active else "forge_builtin_ai",
        "playerPilotSource": (
            "drupal" if player_active and player_resolved else "forge_builtin_ai"
        ),
        "llmAvailable": req.llm_ready,
        "opponentPromptChars": req.opponent.compressed_chars,
        "playerPromptChars": req.player.compressed_chars,
        "opponentPromptOriginalChars": req.opponent.original_chars,
        "playerPromptOriginalChars": req.player.original_chars,
        "opponentPromptPreview": prompt_preview(opp_resolved),
        "playerPromptPreview": prompt_preview(player_resolved),
        "cavemanMode": caveman_mode,
        "cavemanPlayerApplied": req.player.applied,
        "cavemanOpponentApplied": req.opponent.applied,
        "message": message,
    }
