"""Engine selection and pilot-debug metadata for simulation runs."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from caveman_compress import CompressedPrompt, prompt_preview
from pilot_prompts import get_pilot_prompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineRequest:
    """Inputs used to resolve which simulation engine should run."""

    requested: str
    forge_ready: bool
    llm_ready: bool
    use_llm: bool
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
    """Resolve ``auto``/``forge``/``python`` to the engine that will run."""
    if req.requested == "python":
        return "python"
    if req.requested == "forge":
        return "forge" if req.forge_ready else "python"

    opp_resolved = get_pilot_prompt(req.opponent_archetype, req.opp_drupal_prompt)
    player_resolved = req.player_prompt.strip()

    if req.forge_ready:
        if req.llm_ready and (opp_resolved or player_resolved):
            logger.info(
                "auto engine: forge + LLM sidecar (opp=%d chars, player=%d chars)",
                len(opp_resolved),
                len(player_resolved),
            )
        else:
            logger.info(
                "auto engine: forge (built-in AI; sidecar or prompts unavailable)"
            )
        return "forge"

    if req.use_llm and req.llm_ready:
        logger.info("auto engine: useLlm=true -> python (FORGE_JAR not configured)")
        return "python"
    if req.llm_ready and (opp_resolved or player_resolved):
        logger.info(
            "auto engine: python fallback (FORGE_JAR missing; opp=%d chars)",
            len(opp_resolved),
        )
        return "python"
    return "python"


@dataclass(frozen=True)
class PilotInfoRequest:
    """Inputs for building simulation pilot metadata."""

    engine: str
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

    if req.engine == "forge":
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
            "engineUsed": req.engine,
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

    return {
        "engineUsed": req.engine,
        "opponentPilotActive": bool(opp_resolved) and req.llm_ready,
        "playerPilotActive": bool(player_resolved) and req.llm_ready,
        "opponentPilotSource": (
            opp_source if req.llm_ready and opp_resolved else "heuristic"
        ),
        "playerPilotSource": (
            "drupal" if player_resolved and req.llm_ready else "heuristic"
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
        "message": (
            "Python engine: LLM pilots active for sides with prompts when sidecar/Ollama is up. "
            "Otherwise cheapest-spell heuristics apply."
            if req.llm_ready
            else "Python engine: sidecar/Ollama not configured; heuristic pilots only."
        ),
    }
