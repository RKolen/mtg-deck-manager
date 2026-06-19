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

When FORGE_JAR is not set the service runs in mock mode using the built-in
Python engine (faster, less accurate). Set FORGE_JAR to enable real simulation.
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

from deck_registry import (
    fetch_deck_notes,
    fetch_deck_title,
    fetch_meta_deck,
    fetch_player_deck,
)
from engine.game import InteractiveGame, _GameConfig, create_game, get_game, remove_game
from engine.game.action_dispatch import dispatch_game_action
from engine_sim import _BatchConfig, run_simulation as run_python_simulation
from caveman_compress import CompressedPrompt, compress_pilot_prompt
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
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
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
    useLlm: bool = Field(False, description="Use Ollama for MCTS board evaluation (slower)")
    engine: str = Field(
        "auto",
        description=(
            "Simulation engine: 'auto' (Forge when FORGE_JAR is set, else python), "
            "'forge' (Forge JAR — full rules, mulligans, turn logs), or "
            "'python' (LLM pilot prompts — experimental, fewer rules)"
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
    """Return service health and mock-mode status."""
    adapter: ForgeAdapter | None = _state["adapter"]
    mock_mode = adapter.is_mock if adapter is not None else not forge_jar_available()
    return {
        "status": "ok",
        "mock_mode": mock_mode,
        "forge_configured": not mock_mode,
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


@app.post("/simulate")
async def simulate(req: SimulateRequest) -> dict:
    """Run a simulation and return aggregate win-rate statistics."""
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
            requested=req.engine,
            forge_ready=forge_jar_available(),
            llm_ready=llm_ready,
            use_llm=req.useLlm,
            opponent_archetype=req.opponentArchetype,
            opp_drupal_prompt=matchup.opp_pilot_raw,
            player_prompt=matchup.player_pilot.text,
        ),
    )
    pilot_info = build_pilot_info(
        PilotInfoRequest(
            engine=engine,
            opponent_archetype=req.opponentArchetype,
            opp_drupal_prompt=matchup.opp_pilot_raw,
            player=matchup.player_pilot,
            opponent=matchup.opponent_pilot,
            llm_ready=llm_ready,
        ),
    )
    logger.info(
        "Simulation engine=%s matchup=%s vs %s games=%d pilot=%s",
        engine,
        matchup.deck_title,
        req.opponentArchetype,
        req.games,
        pilot_info.get("message"),
    )

    if engine == "forge":
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
    else:
        results = await asyncio.to_thread(
            run_python_simulation,
            matchup.player_deck,
            matchup.opponent_deck,
            req.games,
            _BatchConfig(
                names=(matchup.deck_title, req.opponentArchetype),
                opponent_pilot_prompt=matchup.opponent_pilot.text,
                player_pilot_prompt=matchup.player_pilot.text,
            ),
        )

    if not results:
        raise HTTPException(
            status_code=500,
            detail="Simulation returned no results. Check sim service logs.",
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
    stats["engineUsed"] = engine
    stats["pilotInfo"] = pilot_info
    return stats


# ---------------------------------------------------------------------------
# Interactive game routes
# ---------------------------------------------------------------------------

class StartGameRequest(BaseModel):
    """Request body for POST /game/start."""

    playerDeckId: int
    opponentArchetype: str
    format: str = "Modern"
    onThePlay: bool = True


class GameActionRequest(BaseModel):
    """Request body for POST /game/action.

    Valid actions: keep, mulligan, draw, play_land, cast, pass_priority, go_to_attack,
    toggle_attacker, confirm_attack, skip_attack, end_turn,
    assign_blocker, unassign_blocker, confirm_blocks.
    """

    gameId: str
    action: str
    handIdx: int | None = None
    kickerTimes: int = 0
    entwined: bool = False
    overloaded: bool = False
    bestowTargetUid: str | None = None
    castForMiracle: bool = False
    replicateTimes: int = 0
    paidBuyback: bool = False
    paidCasualty: bool = False
    paidConspire: bool = False
    paidBargain: bool = False
    paidDemonstrate: bool = False
    paidGift: bool = False
    paidFuse: bool = False
    paidAwaken: bool = False
    paidImpending: bool = False
    paidForMirrodin: bool = False
    awakenLandHandIdx: int | None = None
    escalateExtraTargets: int = 0
    bargainSacrificeIds: list[str] = []
    castForCleave: bool = False
    assistMana: int = 0
    craftArtifactIds: list[str] = []
    castForEmerge: bool = False
    castForOffering: bool = False
    castForEvoke: bool = False
    emergeSacrificeIds: list[str] = []
    offeringSacrificeIds: list[str] = []
    forMirrodinSacrificeIds: list[str] = []
    casualtySacrificeIds: list[str] = []
    castForMutate: bool = False
    mutateTargetUid: str | None = None
    spreeModeIndices: list[int] = []
    sneakLandHandIndices: list[int] = []
    castForFreerunning: bool = False
    castForSpectacle: bool = False
    castForSurge: bool = False
    castForMorph: bool = False
    castForDisguise: bool = False
    castForDash: bool = False
    castForBlitz: bool = False
    harmonizeCreatureIds: list[str] = []
    convokeCreatureIds: list[str] = []
    delveGraveyardIndices: list[int] = []
    improviseArtifactIds: list[str] = []
    escapeExileIndices: list[int] = []
    discardHandIdx: int | None = None
    targetUid: str | None = None
    targetPlayer: int | None = None
    permanentUid: str | None = None
    blockerUid: str | None = None
    attackerUid: str | None = None


@app.post("/game/start")
async def game_start(req: StartGameRequest) -> dict:
    """Create a new interactive game session and return the initial state."""
    try:
        player_deck = await asyncio.to_thread(fetch_player_deck, req.playerDeckId)
    except Exception as exc:
        raise HTTPException(502, f"Could not fetch player deck: {exc}") from exc
    if not player_deck:
        raise HTTPException(404, f"Deck {req.playerDeckId} has no cards.")

    player_pilot_raw = await asyncio.to_thread(fetch_deck_notes, req.playerDeckId)
    player_pilot = compress_pilot_prompt(player_pilot_raw)

    try:
        opponent_deck, opp_pilot_raw = await asyncio.to_thread(
            fetch_meta_deck, req.opponentArchetype, req.format
        )
    except Exception as exc:
        raise HTTPException(502, f"Could not fetch meta deck: {exc}") from exc
    if not opponent_deck:
        raise HTTPException(404, f"No meta_deck for '{req.opponentArchetype}' in {req.format}.")

    opponent_pilot = compress_pilot_prompt(
        get_pilot_prompt(req.opponentArchetype, opp_pilot_raw),
    )

    game = create_game(
        player_deck, opponent_deck,
        _GameConfig(
            player_name="You",
            opponent_name=req.opponentArchetype,
            on_the_play=req.onThePlay,
            pilot_prompt=opponent_pilot.text,
            player_pilot_prompt=player_pilot.text,
            pilot_prompt_resolved=True,
        ),
    )
    return game.to_client()


def _dispatch_blocker_action(game: InteractiveGame, req: GameActionRequest) -> dict | None:
    """Dispatch declare-blockers phase actions; return None if action not recognised."""
    if req.action == "assign_blocker":
        assert req.blockerUid is not None and req.attackerUid is not None
        return game.action_assign_blocker(req.blockerUid, req.attackerUid)
    if req.action == "unassign_blocker":
        assert req.blockerUid is not None
        return game.action_unassign_blocker(req.blockerUid)
    if req.action == "confirm_blocks":
        return game.action_confirm_blocks()
    return None


async def _dispatch_action(game: InteractiveGame, req: GameActionRequest) -> dict:
    """Dispatch a single game action and return the updated state dict."""
    if req.action == "end_turn":
        return await asyncio.to_thread(game.action_end_turn)
    result = dispatch_game_action(game, req)
    if result is not None:
        return result
    blocker_result = _dispatch_blocker_action(game, req)
    if blocker_result is not None:
        return blocker_result
    raise HTTPException(400, f"Unknown action '{req.action}'")


@app.post("/game/action")
async def game_action(req: GameActionRequest) -> dict:
    """Submit a player action and return the updated game state."""
    game = get_game(req.gameId)
    if game is None:
        raise HTTPException(404, f"Game {req.gameId} not found.")
    try:
        return await _dispatch_action(game, req)
    except AssertionError as exc:
        raise HTTPException(
            400, f"Invalid action '{req.action}' in phase '{game.phase}'"
        ) from exc


@app.get("/game/state/{game_id}")
async def game_state(game_id: str) -> dict:
    """Return the current state of an active game session."""
    game = get_game(game_id)
    if game is None:
        raise HTTPException(404, f"Game {game_id} not found.")
    return game.to_client()


@app.get("/game/log/{game_id}")
async def game_log(game_id: str) -> dict:
    """Return the full turn-by-turn log for a game session."""
    game = get_game(game_id)
    if game is None:
        raise HTTPException(404, f"Game {game_id} not found.")
    return {"gameId": game_id, "log": game.full_log()}


@app.delete("/game/{game_id}")
async def game_delete(game_id: str) -> dict:
    """Remove a game session and free its memory."""
    remove_game(game_id)
    return {"deleted": game_id}


if __name__ == "__main__":
    from env_loader import load_project_env

    from env_loader import require_env, require_env_int

    load_project_env()
    host = require_env("SIM_HOST")
    port = require_env_int("SIM_PORT")
    uvicorn.run("main:app", host=host, port=port)
