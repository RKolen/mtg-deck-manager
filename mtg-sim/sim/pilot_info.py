"""Engine selection and pilot-debug metadata for simulation runs."""

from __future__ import annotations

import logging
from dataclasses import dataclass

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
    if req.use_llm and req.llm_ready:
        logger.info("auto engine: useLlm=true -> python (LLM pilots + key moments)")
        return "python"
    if req.llm_ready and (opp_resolved or player_resolved):
        logger.info(
            "auto engine: pilot prompts available -> python (opp=%d chars, player=%d chars)",
            len(opp_resolved),
            len(player_resolved),
        )
        return "python"
    if req.forge_ready:
        logger.info(
            "auto engine: no LLM pilots -> forge (Forge built-in AI; prompts ignored)"
        )
        return "forge"
    return "python"


def build_pilot_info(
    engine: str,
    *,
    opponent_archetype: str,
    opp_drupal_prompt: str,
    player_prompt: str,
    llm_ready: bool,
) -> dict:
    """Build API metadata explaining which AI piloted each side."""
    opp_resolved = get_pilot_prompt(opponent_archetype, opp_drupal_prompt)
    player_resolved = player_prompt.strip()
    opp_source = _pilot_source(opponent_archetype, opp_drupal_prompt, opp_resolved)

    if engine == "forge":
        return {
            "engineUsed": engine,
            "opponentPilotActive": False,
            "playerPilotActive": False,
            "opponentPilotSource": "forge_builtin_ai",
            "playerPilotSource": "forge_builtin_ai",
            "llmAvailable": llm_ready,
            "opponentPromptChars": len(opp_resolved),
            "playerPromptChars": len(player_resolved),
            "message": (
                "Forge engine: both sides use Forge built-in AI (Ai1/Ai2). "
                "field_pilot_prompt and field_notes are not applied. "
                "Pass engine=python or use auto with sidecar running to use LLM pilots."
            ),
        }

    return {
        "engineUsed": engine,
        "opponentPilotActive": bool(opp_resolved) and llm_ready,
        "playerPilotActive": bool(player_resolved) and llm_ready,
        "opponentPilotSource": (
            opp_source if llm_ready and opp_resolved else "heuristic"
        ),
        "playerPilotSource": (
            "drupal" if player_resolved and llm_ready else "heuristic"
        ),
        "llmAvailable": llm_ready,
        "opponentPromptChars": len(opp_resolved),
        "playerPromptChars": len(player_resolved),
        "message": (
            "Python engine: LLM pilots active for sides with prompts when sidecar/Ollama is up. "
            "Otherwise cheapest-spell heuristics apply."
            if llm_ready
            else "Python engine: sidecar/Ollama not configured; heuristic pilots only."
        ),
    }
