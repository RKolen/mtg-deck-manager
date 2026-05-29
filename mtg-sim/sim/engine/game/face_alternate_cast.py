"""Shared face-down / dash / blitz alternate cast flags."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaceAlternateCastFlags:
    """Creature alternate cast modes that share mana resolution."""

    cast_for_morph: bool = False
    cast_for_disguise: bool = False
    cast_for_dash: bool = False
    cast_for_blitz: bool = False
