"""Shared sacrifice-based cast flags for validation and stack payment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SacrificeCastFlags:
    """Sacrifice-based optional costs when casting."""

    emerge: bool = False
    evoke: bool = False
    mutate: bool = False
    casualty: bool = False
    bargain: bool = False
