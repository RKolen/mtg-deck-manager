"""
MTG Game Simulation Service — FastAPI app.

Start:  SIM_HOST= SIM_PORT= python main.py
Or:     uvicorn main:app --host $SIM_HOST --port $SIM_PORT

Required environment variables (all defined in .env):
  SIM_HOST       - Bind host
  SIM_PORT       - Bind port
  CORS_ORIGINS   - Comma-separated allowed origins

Forge environment variables:
  FORGE_JAR      - Absolute path to the built forge-gui-desktop JAR
  FORGE_JAVA     - Path to java binary (defaults to "java" on PATH)

Drupal environment variables:
  DRUPAL_URL     - Drupal backend URL for deck/meta data
  DRUPAL_USER    - Drupal API credentials
  DRUPAL_PASS    - Drupal API password

Optional AI environment variables:
  OLLAMA_URL     - Ollama base URL (enables key-moments summary)
  OLLAMA_MODEL   - Chat model for key moments

When FORGE_JAR is not set the service runs in mock mode using the built-in
Python engine (faster, less accurate). Set FORGE_JAR to enable real simulation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import sim_statistics

# Load .env from the same directory as this file (if python-dotenv is installed).
try:
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).parent / ".env")
except ImportError:
    pass

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from deck_registry import fetch_meta_deck, fetch_player_deck
from forge_adapter import ForgeAdapter
from engine.game import create_game, get_game, remove_game

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MTG Simulation Service",
    description="Runs MTG games via Forge and returns win-rate statistics.",
    version="1.0.0",
)

_allow_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
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


@app.get("/health")
def health() -> dict:
    """Return service health and mock-mode status."""
    adapter: ForgeAdapter | None = _state["adapter"]
    return {
        "status": "ok",
        "mock_mode": adapter is None or adapter.is_mock,
    }


@app.post("/simulate")
async def simulate(req: SimulateRequest) -> dict:
    """Run a simulation and return aggregate win-rate statistics."""
    if _state["adapter"] is None:
        _state["adapter"] = ForgeAdapter()

    adapter: ForgeAdapter = _state["adapter"]

    try:
        player_deck = await asyncio.to_thread(fetch_player_deck, req.playerDeckId)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not fetch player deck: {exc}"
        ) from exc

    if not player_deck:
        raise HTTPException(
            status_code=404, detail=f"Deck {req.playerDeckId} has no cards."
        )

    try:
        opponent_deck = await asyncio.to_thread(fetch_meta_deck, req.opponentArchetype, req.format)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not fetch meta deck: {exc}"
        ) from exc

    if not opponent_deck:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No meta_deck found for '{req.opponentArchetype}' in {req.format}. "
                "Populate meta_deck nodes via the MTGGoldfish scraper first."
            ),
        )

    results = await asyncio.to_thread(
        adapter.run_simulation,
        player_deck,
        opponent_deck,
        req.games,
        (f"Deck #{req.playerDeckId}", req.opponentArchetype),
    )

    if not results:
        raise HTTPException(
            status_code=500,
            detail="Simulation returned no results. Check sim service logs.",
        )

    return await asyncio.to_thread(
        sim_statistics.compute_statistics,
        results,
        f"Deck #{req.playerDeckId}",
        req.opponentArchetype,
        req.format,
        not adapter.is_mock,
    )


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

    Valid actions: keep, mulligan, draw, play_land, cast, go_to_attack,
    toggle_attacker, confirm_attack, skip_attack, end_turn,
    assign_blocker, unassign_blocker, confirm_blocks.
    """

    gameId: str
    action: str
    handIdx: int | None = None
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

    try:
        opponent_deck = await asyncio.to_thread(fetch_meta_deck, req.opponentArchetype, req.format)
    except Exception as exc:
        raise HTTPException(502, f"Could not fetch meta deck: {exc}") from exc
    if not opponent_deck:
        raise HTTPException(404, f"No meta_deck for '{req.opponentArchetype}' in {req.format}.")

    game = create_game(
        player_deck, opponent_deck,
        player_name="You",
        opponent_name=req.opponentArchetype,
        on_the_play=req.onThePlay,
    )
    return game.to_client()


def _dispatch_blocker_action(game, req: GameActionRequest) -> dict | None:
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


async def _dispatch_action(game, req: GameActionRequest) -> dict:
    """Dispatch a single game action and return the updated state dict.

    Simple actions (no arguments) are resolved via a lookup table.
    Actions that require request parameters are handled explicitly.
    """
    simple: dict[str, object] = {
        "keep": game.action_keep,
        "mulligan": game.action_mulligan,
        "draw": game.action_draw,
        "go_to_attack": game.action_go_to_attack,
        "confirm_attack": game.action_confirm_attack,
        "skip_attack": game.action_skip_attack,
    }
    if req.action in simple:
        return simple[req.action]()  # type: ignore[operator]
    if req.action == "play_land":
        assert req.handIdx is not None
        return game.action_play_land(req.handIdx)
    if req.action == "cast":
        assert req.handIdx is not None
        return game.action_cast(req.handIdx, req.targetUid, req.targetPlayer)
    if req.action == "toggle_attacker":
        assert req.permanentUid is not None
        return game.action_toggle_attacker(req.permanentUid)
    if req.action == "end_turn":
        return await asyncio.to_thread(game.action_end_turn)
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
    host = os.environ.get("SIM_HOST", "")
    port = int(os.environ.get("SIM_PORT", "0"))
    uvicorn.run("main:app", host=host, port=port)
