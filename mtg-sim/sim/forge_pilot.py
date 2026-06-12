"""Forge LLM pilot configuration and .dck metadata helpers."""

from __future__ import annotations

import logging
import os
import pathlib
import subprocess
from dataclasses import dataclass
from typing import Optional

from env_loader import require_env, require_env_int

logger = logging.getLogger(__name__)

FORGE_JAR: str = os.environ.get("FORGE_JAR", "")

_COMBO_ARCHETYPE_KEYWORDS = (
    "storm", "belcher", "ad nauseam", "amulet", "living end", "grinding",
)


@dataclass(frozen=True)
class ForgePilotConfig:
    """LLM pilot options passed to Forge's sim command."""

    player_pilot_prompt: str = ""
    opponent_pilot_prompt: str = ""
    opponent_archetype: str = ""
    pilot_url: str = ""
    pilot_timeout: int = 10

    def pilot_active(self) -> bool:
        """Return True when Forge should call the sidecar for at least one deck."""
        if not self.pilot_url.strip():
            return False
        return bool(
            self.player_pilot_prompt.strip() or self.opponent_pilot_prompt.strip()
        )


@dataclass(frozen=True)
class ForgeSimOptions:
    """Optional Forge batch settings beyond card lists and game count."""

    deck_names: tuple[str, str] = ("Player", "Opponent")
    pilot: Optional[ForgePilotConfig] = None


def format_ai_hints(pilot_prompt: str = "", pilot_mode: str = "") -> Optional[str]:
    """Build a Forge .dck AiHints metadata line, or None when empty."""
    parts: list[str] = []
    if pilot_prompt.strip():
        text = " ".join(pilot_prompt.split())
        parts.append(f"PilotPrompt${text}")
    if pilot_mode.strip():
        parts.append(f"PilotMode${pilot_mode.strip()}")
    if not parts:
        return None
    return "AiHints=" + " | ".join(parts)


def forge_pilot_mode_for_archetype(archetype: str) -> str:
    """Return Forge PilotMode hint value for combo archetypes (e.g. storm)."""
    lower = archetype.lower()
    if any(keyword in lower for keyword in _COMBO_ARCHETYPE_KEYWORDS):
        return "combo"
    return ""


def resolve_forge_pilot_config(
    player_prompt: str,
    opponent_prompt: str,
    opponent_archetype: str,
) -> ForgePilotConfig:
    """Build pilot config from env and resolved Drupal/builtin prompts."""
    needs_pilot = bool(player_prompt.strip() or opponent_prompt.strip())
    pilot_url = ""
    pilot_timeout = 0
    if needs_pilot:
        pilot_url = require_env("SIDECAR_URL").rstrip("/")
        pilot_timeout = require_env_int("FORGE_PILOT_TIMEOUT")
    logger.info(
        "Forge LLM pilot (player_chars=%d, opp_chars=%d)",
        len(player_prompt.strip()),
        len(opponent_prompt.strip()),
    )
    return ForgePilotConfig(
        player_pilot_prompt=player_prompt.strip(),
        opponent_pilot_prompt=opponent_prompt.strip(),
        opponent_archetype=opponent_archetype,
        pilot_url=pilot_url,
        pilot_timeout=pilot_timeout,
    )


def deck_ai_hints(
    pilot_prompt: str,
    pilot_mode: str = "",
) -> Optional[str]:
    """Return AiHints line when this deck has a pilot prompt."""
    if not pilot_prompt.strip():
        return None
    return format_ai_hints(pilot_prompt, pilot_mode)


def build_forge_cmd(
    p_name: str,
    o_name: str,
    n_games: int,
    pilot_cfg: ForgePilotConfig,
) -> list[str]:
    """Assemble the java -jar forge sim command line."""
    cmd = [
        require_env("FORGE_JAVA"), "-jar", FORGE_JAR,
        "sim",
        "-d", f"{p_name}.dck", f"{o_name}.dck",
        "-n", str(n_games),
        "-c", "60",
    ]
    if pilot_cfg.pilot_active():
        cmd.extend([
            "-pilot-url", pilot_cfg.pilot_url,
            "-pilot-timeout", str(pilot_cfg.pilot_timeout),
        ])
    return cmd


def invoke_forge(cmd: list[str], n_games: int) -> str:
    """Run Forge subprocess; return stdout or empty string on failure."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=n_games * 90,
            check=False,
            cwd=str(pathlib.Path(FORGE_JAR).parent),
        )
    except subprocess.TimeoutExpired:
        logger.error("Forge simulation timed out after %d games", n_games)
        return ""
    except FileNotFoundError:
        logger.error("Java not found. Set FORGE_JAVA to the java binary path.")
        return ""

    if proc.returncode != 0:
        logger.error("Forge exited %d: %s", proc.returncode, proc.stderr[:500])
    return proc.stdout
