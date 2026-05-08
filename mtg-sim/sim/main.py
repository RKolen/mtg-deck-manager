"""
MTG Game Simulation Service — FastAPI app.

Start:  SIM_HOST= SIM_PORT= python main.py
Or:     uvicorn main:app --host $SIM_HOST --port $SIM_PORT

Required environment variables (for python main.py only):
  SIM_HOST       - Bind host
  SIM_PORT       - Bind port

Forge environment variables (all required to enable real Forge mode):
  FORGE_JAR      - Absolute path to the built forge-ai JAR
  FORGE_HOST     - Hostname of the Forge socket server
  FORGE_PORT     - Port of the Forge socket server

Drupal environment variables:
  DRUPAL_URL     - Drupal backend URL for deck/meta data
  DRUPAL_USER    - Drupal API credentials
  DRUPAL_PASS    - Drupal API password

Optional AI environment variables:
  OLLAMA_URL     - Ollama base URL (enables key-moments summary)
  OLLAMA_MODEL   - Chat model for key moments

When Forge env vars are not set the service runs in mock mode — games return
random outcomes for validating the statistics pipeline and Gatsby UI.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sim_statistics

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from deck_registry import fetch_meta_deck, fetch_player_deck
from forge_adapter import ForgeAdapter
from mcts import MctsAgent, RandomAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MTG Simulation Service",
    description="Runs MTG games via Forge and returns win-rate statistics.",
    version="1.0.0",
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

    player_agent = MctsAgent(rollouts_per_action=15, use_llm=req.useLlm, player_idx=0)
    opponent_agent = RandomAgent()

    results = []
    for i in range(req.games):
        game_id = adapter.start_game(player_deck, opponent_deck)
        result = adapter.run_game(game_id, player_agent, opponent_agent, on_the_play=i % 2 == 0)
        results.append(result)

    return await asyncio.to_thread(
        sim_statistics.compute_statistics,
        results,
        f"Deck #{req.playerDeckId}",
        req.opponentArchetype,
        req.format,
        True,
    )


if __name__ == "__main__":
    host = os.environ.get("SIM_HOST", "")
    port_str = os.environ.get("SIM_PORT", "")
    if not host or not port_str:
        raise RuntimeError("Set SIM_HOST and SIM_PORT env vars before starting.")
    uvicorn.run("main:app", host=host, port=int(port_str))
