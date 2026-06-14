"""Shared sacrifice-based cast flags for validation and stack payment."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _ArtifactCastSacFlags:
    """Artifact-specific sacrifice costs."""

    offering: bool = False
    for_mirrodin: bool = False


@dataclass
class SacrificeCastFlags:
    """Sacrifice-based optional costs when casting."""

    emerge: bool = False
    evoke: bool = False
    mutate: bool = False
    casualty: bool = False
    bargain: bool = False
    gift: bool = False
    artifact: _ArtifactCastSacFlags = field(default_factory=_ArtifactCastSacFlags)
