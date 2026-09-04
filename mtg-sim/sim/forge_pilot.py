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
# JVM max heap for the Forge sim subprocess. Forge otherwise defaults to ~1/4 of
# system RAM (~7.8 GB here), which stacks with the desktop/IDE and risks OOM; sim
# mode runs comfortably in a few GB. Override with FORGE_MAX_HEAP (e.g. "2g").
FORGE_MAX_HEAP: str = os.environ.get("FORGE_MAX_HEAP", "4g")

_COMBO_ARCHETYPE_KEYWORDS = (
    "storm", "belcher", "ad nauseam", "amulet", "living end", "grinding",
)

# Forge's -c flag is a wall clock on the WHOLE match, not on one decision: when
# it expires Forge prints "Stopping slow match as draw" and ends the game as a
# draw (SimulateMatch.simulateSingleMatch). Its 120s default assumes Forge's
# built-in AI, which decides in microseconds. An LLM pilot takes seconds per
# decision, so a piloted match needs a clock derived from the pilot budget —
# otherwise the first pilot call alone exhausts it and every game draws on
# turn 0.
#
# The clock is a hang detector, not a schedule: a game that plays out faster
# still finishes early, so it is sized generously.

# Pilot decisions a full game is expected to need (~25 turns × 2 players ×
# ~3 decisions each).
_PILOT_DECISIONS_PER_GAME = 150

# Share of its timeout ceiling a steady-state pilot call actually uses. Only the
# first call, which pays the model load, approaches FORGE_PILOT_TIMEOUT.
_PILOT_AVG_LATENCY_RATIO = 0.05

# Match clock for Forge's built-in AI, which needs no LLM round trips. Also the
# floor for a piloted match.
_BUILTIN_AI_CLOCK_SECONDS = 120

# Slack added to the Forge subprocess timeout for JVM start-up and card-DB load,
# so the subprocess is never killed before its own match clock can fire.
_FORGE_STARTUP_SECONDS = 120


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


@dataclass(frozen=True)
class ForgeRunBudget:
    """Nested time budgets for one Forge batch, in seconds."""

    clock: int
    subprocess_timeout: int


def forge_sim_clock(pilot_cfg: ForgePilotConfig) -> int:
    """Seconds Forge may spend on one match before calling it a draw (-c).

    Covers every pilot decision in the game, not just one, so it is derived
    from the per-call pilot budget rather than fixed.
    """
    if not pilot_cfg.pilot_active():
        return _BUILTIN_AI_CLOCK_SECONDS
    # One full-ceiling call to absorb the cold model load, then a steady-state
    # budget for the remaining decisions of the game.
    cold_start = pilot_cfg.pilot_timeout
    steady = (
        pilot_cfg.pilot_timeout
        * _PILOT_AVG_LATENCY_RATIO
        * _PILOT_DECISIONS_PER_GAME
    )
    return max(_BUILTIN_AI_CLOCK_SECONDS, int(cold_start + steady))


def forge_run_budget(n_games: int, pilot_cfg: ForgePilotConfig) -> ForgeRunBudget:
    """Build the match clock and the subprocess timeout that must contain it.

    The subprocess timeout exceeds every match's own clock so Forge stops slow
    games itself and still prints its results, instead of being killed with
    nothing parseable on stdout.
    """
    clock = forge_sim_clock(pilot_cfg)
    return ForgeRunBudget(
        clock=clock,
        subprocess_timeout=n_games * clock + _FORGE_STARTUP_SECONDS,
    )


def build_forge_cmd(
    p_name: str,
    o_name: str,
    n_games: int,
    pilot_cfg: ForgePilotConfig,
) -> list[str]:
    """Assemble the java -jar forge sim command line."""
    return [
        require_env("FORGE_JAVA"), f"-Xmx{FORGE_MAX_HEAP}", "-jar", FORGE_JAR,
        "sim",
        "-d", f"{p_name}.dck", f"{o_name}.dck",
        "-n", str(n_games),
        "-c", str(forge_sim_clock(pilot_cfg)),
    ] + ([
        "-pilot-url", pilot_cfg.pilot_url,
        "-pilot-timeout", str(pilot_cfg.pilot_timeout),
    ] if pilot_cfg.pilot_active() else [])


def _forge_work_dir() -> str:
    """Directory to run Forge from — must contain Forge's res/ (card DB, languages).

    Forge resolves res/ relative to its working directory and fails its static
    initialization without it. The JAR lives in forge-gui-desktop/target/, which
    `mvn clean` wipes and which holds no res/, so locate the res-bearing dir
    (typically forge-gui/) by walking up from the JAR. Falls back to the JAR's
    own directory when no res/ is found.
    """
    jar = pathlib.Path(FORGE_JAR).resolve()
    for ancestor in jar.parents:
        if (ancestor / "res").is_dir():
            return str(ancestor)
        gui_res = ancestor / "forge-gui" / "res"
        if gui_res.is_dir():
            return str(gui_res.parent)
    return str(jar.parent)


def invoke_forge(cmd: list[str], n_games: int, timeout: int) -> str:
    """Run Forge subprocess; return stdout or empty string on failure."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=_forge_work_dir(),
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "Forge subprocess killed after %ds without finishing %d games. "
            "Its own match clock should have stopped slow games first — check "
            "FORGE_PILOT_TIMEOUT and whether the sidecar is responding.",
            timeout,
            n_games,
        )
        return ""
    except FileNotFoundError:
        logger.error("Java not found. Set FORGE_JAVA to the java binary path.")
        return ""

    if proc.returncode != 0:
        logger.error("Forge exited %d: %s", proc.returncode, proc.stderr[:500])
    return proc.stdout
