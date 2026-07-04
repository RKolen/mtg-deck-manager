"""Shared alternate-cast mode flags used by announce validation and mana."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AltCastModeFlags:
    """Warp, web-slinging, converted, and specialize alternate casts."""

    warp: bool = False
    web_slinging: bool = False
    converted: bool = False
    specialize: bool = False
