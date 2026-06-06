"""Host-side AI sidecar for MTG simulation and Drupal AI features."""

from __future__ import annotations

import pathlib
import sys

_SIM_DIR = pathlib.Path(__file__).resolve().parent.parent / "sim"
if str(_SIM_DIR) not in sys.path:
    sys.path.insert(0, str(_SIM_DIR))
