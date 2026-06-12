"""Entry point for the MTG AI sidecar."""

from __future__ import annotations

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

    from env_loader import require_env, require_env_int

    load_project_env()
    host = require_env("SIDECAR_HOST")
    port = require_env_int("SIDECAR_PORT")
    uvicorn.run("sidecar.app:app", host=host, port=port)
