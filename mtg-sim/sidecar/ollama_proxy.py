"""Transparent Ollama API proxy so DDEV can reach host Ollama via the sidecar."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from ollama_http import OLLAMA_URL

router = APIRouter()

_HOP_HEADERS = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
})


def _ollama_base() -> str:
    if not OLLAMA_URL:
        raise HTTPException(status_code=503, detail="Ollama not configured on sidecar host")
    return OLLAMA_URL.rstrip("/")


def _forward_headers(request: Request) -> dict[str, str]:
    return {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _HOP_HEADERS
    }


async def _proxy_request(request: Request, upstream_path: str) -> Response:
    """Forward a request to the host Ollama process."""
    base = _ollama_base()
    url = f"{base}/{upstream_path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            upstream = await client.request(
                request.method,
                url,
                content=body,
                headers=_forward_headers(request),
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama proxy failed: {exc}") from exc

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in _HOP_HEADERS
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )


@router.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_ollama_api(path: str, request: Request) -> Response:
    """Proxy native Ollama /api/* routes."""
    return await _proxy_request(request, f"api/{path}")


@router.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_ollama_openai(path: str, request: Request) -> Response:
    """Proxy OpenAI-compatible /v1/* routes used by Drupal's ai module."""
    return await _proxy_request(request, f"v1/{path}")
