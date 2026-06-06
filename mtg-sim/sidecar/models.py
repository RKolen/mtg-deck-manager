"""Pydantic request and response models for the MTG AI sidecar."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    ollama_configured: bool
    model: str


class PilotPickRequest(BaseModel):
    """LLM pilot decision request."""

    question: str
    options: list[str] = Field(..., min_length=1)
    state: dict = Field(default_factory=dict)
    system_prompt: str = ""


class PilotPickResponse(BaseModel):
    """LLM pilot decision response."""

    index: int
    reasoning: str


class GenerateRequest(BaseModel):
    """Open-ended text generation request."""

    prompt: str
    temperature: float = 0.2
    max_tokens: int = 512


class GenerateResponse(BaseModel):
    """Generated text response."""

    text: str
