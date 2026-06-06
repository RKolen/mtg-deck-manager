"""Load MTG environment variables from the repo-root .env file."""

from __future__ import annotations

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
