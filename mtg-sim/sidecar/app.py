"""FastAPI application for the host-side MTG AI sidecar."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from sidecar.models import (
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    PilotPickRequest,
    PilotPickResponse,
)
from sidecar.ollama_backend import OLLAMA_MODEL, generate_text, is_configured, pilot_pick

app = FastAPI(
    title="MTG AI Sidecar",
    description=(
        "Host-side LLM boundary for simulation pilots and optional Drupal AI calls. "
        "Runs outside DDEV and proxies to host Ollama."
    ),
    version="1.0.0",
)


@app.get("/")
def root() -> dict:
    """Return service identity and useful endpoint paths."""
    return {
        "service": "MTG AI Sidecar",
        "health": "/health",
        "pilot_pick": "/pilot-pick",
        "generate": "/generate",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service health and Ollama configuration status."""
    return HealthResponse(
        status="ok",
        ollama_configured=is_configured(),
        model=OLLAMA_MODEL,
    )


@app.post("/pilot-pick", response_model=PilotPickResponse)
def pilot_pick_endpoint(req: PilotPickRequest) -> PilotPickResponse:
    """Choose the best pilot action from a numbered option list."""
    if not is_configured():
        raise HTTPException(status_code=503, detail="Ollama not configured on sidecar host")
    try:
        index, reasoning = pilot_pick(
            req.question,
            req.options,
            req.state,
            system_prompt=req.system_prompt,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PilotPickResponse(index=index, reasoning=reasoning)


@app.post("/generate", response_model=GenerateResponse)
def generate_endpoint(req: GenerateRequest) -> GenerateResponse:
    """Run an open-ended Ollama generation call."""
    if not is_configured():
        raise HTTPException(status_code=503, detail="Ollama not configured on sidecar host")
    text = generate_text(req.prompt, temperature=req.temperature, max_tokens=req.max_tokens)
    if not text:
        raise HTTPException(status_code=502, detail="Ollama returned an empty response")
    return GenerateResponse(text=text)
