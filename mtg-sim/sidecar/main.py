"""Entry point for the MTG AI sidecar."""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    import pathlib
    import sys

    _sim_dir = pathlib.Path(__file__).resolve().parent.parent / "sim"
    if str(_sim_dir) not in sys.path:
        sys.path.insert(0, str(_sim_dir))
    from env_loader import load_project_env

    load_project_env()
    host = os.environ.get("SIDECAR_HOST", "127.0.0.1")
    port = int(os.environ.get("SIDECAR_PORT", "8010"))
    uvicorn.run("sidecar.app:app", host=host, port=port)
