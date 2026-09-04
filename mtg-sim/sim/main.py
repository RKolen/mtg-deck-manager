"""
MTG Game Simulation Service — FastAPI app.

Start:  SIM_HOST= SIM_PORT= python main.py
Or:     uvicorn main:app --host $SIM_HOST --port $SIM_PORT

Required environment variables (repo-root .env — see /.env.example):
  SIM_HOST       - Bind host
  SIM_PORT       - Bind port
  CORS_ORIGINS   - Comma-separated allowed origins

Forge environment variables:
  FORGE_JAR           - Absolute path to the built forge-gui-desktop JAR
  FORGE_JAVA          - Path to java binary
  FORGE_PILOT_TIMEOUT - Sidecar timeout seconds for Forge LLM pilots

Drupal environment variables:
  DRUPAL_URL     - Drupal backend URL for deck/meta data
  DRUPAL_USER    - Drupal API credentials
  DRUPAL_PASS    - Drupal API password

Optional AI environment variables:
  SIDECAR_URL    - Host-side AI sidecar (preferred; keeps inference out of DDEV)
  OLLAMA_URL     - Direct Ollama URL (fallback when SIDECAR_URL is unset)
  OLLAMA_MODEL   - Chat model for pilot decisions and key moments
  CAVEMAN_PILOT  - Pilot prompt compression: rules (default), llm, or off
  CAVEMAN_PILOT_MIN_CHARS - Skip compression below this length (default 120)
  SIM_BATCH_SIZE - Games per Forge subprocess chunk (default 5)

FORGE_JAR must point at an existing Forge desktop JAR. The service does not
fall back to a heuristic engine when the JAR is missing or a run fails.
"""

from __future__ import annotations

import asyncio
import logging
import os
import warnings
from dataclasses import dataclass

import sim_statistics
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from caveman_compress import CompressedPrompt, compress_pilot_prompt
from deck_registry import (
    fetch_deck_notes,
    fetch_deck_title,
    fetch_meta_deck,
    fetch_player_deck,
)
from forge_adapter import ForgeAdapter, ForgeSimOptions, forge_jar_available
from forge_pilot import resolve_forge_pilot_config
from game_log_emitter import emit_game_logs
from llm_client import is_configured as llm_is_configured
from pilot_info import EngineRequest, PilotInfoRequest, build_pilot_info, resolve_sim_engine
from pilot_prompts import get_pilot_prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

app = FastAPI(
    title="MTG Simulation Service",
    description="Runs MTG games via Forge and returns win-rate statistics.",
    version="1.0.0",
)


def _cors_origins() -> list[str]:
    """Return comma-separated CORS_ORIGINS from the environment."""
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw:
        raise RuntimeError(
            "CORS_ORIGINS must be set in the repo-root .env file (comma-separated)."
        )
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Module-level container avoids the global statement while keeping a single
# long-lived adapter instance shared across requests.
_state: dict = {"adapter": None}


class SimulateRequest(BaseModel):
    """Request body for POST /simulate."""

    playerDeckId: int = Field(..., description="Drupal node ID of the player's deck")
    opponentArchetype: str = Field(..., description="Archetype name matching a meta_deck title")
    format: str = Field("Modern", description="MTG format")
    games: int = Field(50, ge=1, le=200, description="Number of games to simulate (max 200)")
    useLlm: bool = Field(
        False,
        description="Generate LLM key-moment summaries from finished Forge games",
    )
    engine: str = Field(
        "auto",
        description=(
            "Simulation engine: 'auto' and 'forge' both run the local Forge JAR. "
            "The Python interactive engine is no longer available."
        ),
    )
    pilotSide: str = Field(
        "auto",
        description=(
            "Deprecated Forge override; each deck with a prompt is LLM-piloted when "
            "SIDECAR_URL is set. field_notes for your deck, archetype prompt for opponent."
        ),
    )


@app.get("/")
def root() -> dict:
    """Return service identity and useful endpoint paths."""
    return {
        "service": "MTG Simulation Service",
        "health": "/health",
        "simulate": "/simulate",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict:
    """Return service health and whether the local Forge JAR is configured."""
    configured = forge_jar_available()
    return {
        "status": "ok" if configured else "degraded",
        "forge_configured": configured,
    }


@dataclass(frozen=True)
class _SimMatchup:
    """Deck lists and caveman-compressed pilot prompts for one simulation."""

    deck_title: str
    player_deck: list
    opponent_deck: list
    player_pilot: CompressedPrompt
    opponent_pilot: CompressedPrompt
    opp_pilot_raw: str


async def _load_sim_matchup(deck_id: int, archetype: str, fmt: str) -> _SimMatchup:
    """Fetch decks and compress pilot prompts for a gauntlet simulation."""
    player_deck = await asyncio.to_thread(fetch_player_deck, deck_id)
    if not player_deck:
        raise HTTPException(status_code=404, detail=f"Deck {deck_id} has no cards.")
    deck_title = await asyncio.to_thread(fetch_deck_title, deck_id)
    player_pilot = compress_pilot_prompt(
        await asyncio.to_thread(fetch_deck_notes, deck_id),
    )
    try:
        opponent_deck, opp_pilot_raw = await asyncio.to_thread(
            fetch_meta_deck, archetype, fmt,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not fetch meta deck: {exc}",
        ) from exc
    if not opponent_deck:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No meta_deck found for '{archetype}' in {fmt}. "
                "Populate meta_deck nodes via the MTGGoldfish scraper first."
            ),
        )
    opponent_pilot = compress_pilot_prompt(
        get_pilot_prompt(archetype, opp_pilot_raw),
    )
    return _SimMatchup(
        deck_title=deck_title,
        player_deck=player_deck,
        opponent_deck=opponent_deck,
        player_pilot=player_pilot,
        opponent_pilot=opponent_pilot,
        opp_pilot_raw=opp_pilot_raw,
    )


def _require_forge_engine(requested: str) -> None:
    """Reject unsupported engines and a missing local Forge JAR."""
    if requested not in ("auto", "forge"):
        raise HTTPException(
            status_code=400,
            detail="engine must be 'auto' or 'forge'. The Python engine is discontinued.",
        )
    if not forge_jar_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "FORGE_JAR is not set or the file is missing. "
                "Point FORGE_JAR at the Forge desktop JAR and restart the sim service."
            ),
        )


@app.post("/simulate")
async def simulate(req: SimulateRequest) -> dict:
    """Run a Forge simulation and return aggregate win-rate statistics."""
    _require_forge_engine(req.engine)

    if _state["adapter"] is None:
        _state["adapter"] = ForgeAdapter()

    adapter: ForgeAdapter = _state["adapter"]

    try:
        matchup = await _load_sim_matchup(
            req.playerDeckId, req.opponentArchetype, req.format,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not fetch player deck: {exc}",
        ) from exc

    llm_ready = llm_is_configured()
    engine = resolve_sim_engine(
        EngineRequest(
            llm_ready=llm_ready,
            opponent_archetype=req.opponentArchetype,
            opp_drupal_prompt=matchup.opp_pilot_raw,
            player_prompt=matchup.player_pilot.text,
        ),
    )
    pilot_info = build_pilot_info(
        PilotInfoRequest(
            opponent_archetype=req.opponentArchetype,
            opp_drupal_prompt=matchup.opp_pilot_raw,
            player=matchup.player_pilot,
            opponent=matchup.opponent_pilot,
            llm_ready=llm_ready,
        ),
    )
    logger.info(
        "Simulation engine=%s playerDeckId=%s vs archetype=%s games=%d pilot=%s",
        engine,
        req.playerDeckId,
        req.opponentArchetype,
        req.games,
        pilot_info.get("message"),
    )

    forge_pilot = resolve_forge_pilot_config(
        matchup.player_pilot.text,
        matchup.opponent_pilot.text,
        req.opponentArchetype,
    )
    results = await asyncio.to_thread(
        adapter.run_simulation,
        matchup.player_deck,
        matchup.opponent_deck,
        req.games,
        options=ForgeSimOptions(
            deck_names=(matchup.deck_title, req.opponentArchetype),
            pilot=forge_pilot,
        ),
    )

    if not results:
        raise HTTPException(
            status_code=503,
            detail=(
                "Forge returned no results. Check that Java can run FORGE_JAR "
                "and see the sim service logs."
            ),
        )

    emit_game_logs(results, matchup.deck_title, req.opponentArchetype)

    stats = await asyncio.to_thread(
        sim_statistics.compute_statistics,
        results,
        sim_statistics.MatchupConfig(
            player_deck_name=matchup.deck_title,
            opponent_archetype=req.opponentArchetype,
            fmt=req.format,
            generate_moments=req.useLlm,
        ),
    )
    stats["engineUsed"] = "forge"
    stats["engineRequested"] = engine
    stats["pilotInfo"] = pilot_info
    return stats


if __name__ == "__main__":
    from env_loader import load_project_env
    from env_loader import require_env, require_env_int

    load_project_env()
    host = require_env("SIM_HOST")
    port = require_env_int("SIM_PORT")
    uvicorn.run("main:app", host=host, port=port)
