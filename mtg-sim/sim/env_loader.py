"""Load MTG environment variables from the repo-root .env file."""

from __future__ import annotations

import os
import pathlib

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def load_project_env() -> None:
    """Load repo-root .env, then optional mtg-sim/sim/.env overrides."""
    if load_dotenv is None:
        return
    repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
    load_dotenv(repo_root / ".env")
    local_env = pathlib.Path(__file__).resolve().parent / ".env"
    if local_env.is_file():
        load_dotenv(local_env, override=True)


def require_env(name: str) -> str:
    """Return a required environment variable or raise."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            "Set it in the repo-root .env file."
        )
    return value


def require_env_int(name: str) -> int:
    """Return a required integer environment variable or raise."""
    raw = require_env(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got: {raw!r}") from exc


def require_env_float(name: str) -> float:
    """Return a required float environment variable or raise."""
    raw = require_env(name)
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number, got: {raw!r}") from exc
