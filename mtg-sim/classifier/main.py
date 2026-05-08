"""
MTG Deck Deduction Classifier — FastAPI service.

Start:  CLASSIFIER_HOST= CLASSIFIER_PORT= python main.py
Or:     uvicorn main:app --host $CLASSIFIER_HOST --port $CLASSIFIER_PORT

Required environment variables (for python main.py only):
  CLASSIFIER_HOST - Bind host
  CLASSIFIER_PORT - Bind port

Optional environment variables (for /train endpoint):
  DRUPAL_URL      - Drupal site base URL
  DRUPAL_USER     - HTTP Basic Auth username
  DRUPAL_PASS     - HTTP Basic Auth password
"""

from __future__ import annotations

import logging
import os

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from classifier import DeckClassifier

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="MTG Deck Deduction Classifier",
    description="Infers opponent archetype from observed plays.",
    version="1.0.0",
)

_classifier = DeckClassifier()


class Play(BaseModel):
    """A single observed card play from the opponent."""

    card_name: str
    type: str = ""
    colors: list[str] = []


class ClassifyRequest(BaseModel):
    """Request body for POST /classify."""

    plays: list[Play]


class ArchetypeProbability(BaseModel):
    """One archetype with its predicted probability."""

    name: str
    probability: float


class ClassifyResponse(BaseModel):
    """Response body for POST /classify."""

    archetypes: list[ArchetypeProbability]


class TrainResponse(BaseModel):
    """Response body for POST /train."""

    status: str
    archetypes_trained: int
    archetypes: list[str]


@app.get("/health")
def health() -> dict:
    """Return service health and model status."""
    return {
        "status": "ok",
        "model_loaded": _classifier.pipeline is not None,
        "archetypes": len(_classifier.archetypes),
    }


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> ClassifyResponse:
    """Classify observed plays into archetype probabilities."""
    result = _classifier.classify([p.model_dump() for p in req.plays])
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return ClassifyResponse(archetypes=[
        ArchetypeProbability(**a) for a in result["archetypes"]
    ])


@app.post("/train", response_model=TrainResponse)
def train() -> TrainResponse:
    """Fetch meta_deck nodes from Drupal and retrain the classifier."""
    drupal_url = os.environ.get("DRUPAL_URL", "")
    api_user = os.environ.get("DRUPAL_USER", "")
    api_pass = os.environ.get("DRUPAL_PASS", "")

    if not drupal_url:
        raise HTTPException(status_code=500, detail="DRUPAL_URL env var not set.")

    count = _classifier.train_from_drupal(drupal_url, api_user, api_pass)
    return TrainResponse(
        status="trained" if count > 0 else "no_data",
        archetypes_trained=count,
        archetypes=_classifier.archetypes,
    )


if __name__ == "__main__":
    host = os.environ.get("CLASSIFIER_HOST", "")
    port_str = os.environ.get("CLASSIFIER_PORT", "")
    if not host or not port_str:
        raise RuntimeError("Set CLASSIFIER_HOST and CLASSIFIER_PORT env vars before starting.")
    uvicorn.run("main:app", host=host, port=int(port_str))
