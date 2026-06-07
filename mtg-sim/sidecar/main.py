"""Entry point for the MTG AI sidecar."""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    import pathlib
    import sys

    _mtg_sim = pathlib.Path(__file__).resolve().parent.parent
    _sim_dir = _mtg_sim / "sim"
    for path in (_mtg_sim, _sim_dir):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from env_loader import load_project_env

    load_project_env()
    host = os.environ.get("SIDECAR_HOST", "127.0.0.1")
    port = int(os.environ.get("SIDECAR_PORT", "8010"))
    uvicorn.run("sidecar.app:app", host=host, port=port)
