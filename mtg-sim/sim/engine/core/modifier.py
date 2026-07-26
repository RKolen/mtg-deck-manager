"""Continuous-effect modifiers for the CR 613 layer system."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

_ts_counter: itertools.count[int] = itertools.count(1)


def next_modifier_timestamp() -> int:
    """Allocate a timestamp for ordering simultaneous continuous effects."""
    return next(_ts_counter)


@dataclass
class _ModifierLayer:
    """Layer ordering metadata for one modifier."""

    layer: int = 7
    sublayer: str = ""
    timestamp: int = field(default_factory=next_modifier_timestamp)
    duration: str = "permanent"


@dataclass
class _ModifierPt:
    """Power and toughness changes applied by one modifier."""

    set_power: int | None = None
    set_toughness: int | None = None
    power_delta: int = 0
    toughness_delta: int = 0
    switch_pt: bool = False


@dataclass
class _ModifierCharacteristics:
    """Characteristic changes for continuous-effect layers 2, 4, and 5."""

    controller_override: int | None = None
    added_types: tuple[str, ...] = ()
    removed_types: tuple[str, ...] = ()
    set_colors: tuple[str, ...] | None = None
    granted_keywords: tuple[str, ...] = ()


@dataclass
class Modifier:
    """A continuous effect currently applied to a permanent.

    Layers 2 and 4-7 are applied in ``continuous.py`` (CR 613).
    """

    source_obj_id: int = 0
    layer_info: _ModifierLayer = field(default_factory=_ModifierLayer)
    pt: _ModifierPt = field(default_factory=_ModifierPt)
    characteristics: _ModifierCharacteristics = field(
        default_factory=_ModifierCharacteristics,
    )
    remove_all_abilities: bool = False
    cda_from_graveyard_count: bool = False

    @property
    def layer(self) -> int:
        """Continuous effect layer number."""
        return self.layer_info.layer

    @layer.setter
    def layer(self, value: int) -> None:
        """Set continuous effect layer number."""
        self.layer_info.layer = value

    @property
    def sublayer(self) -> str:
        """Layer 7 sublayer label."""
        return self.layer_info.sublayer

    @sublayer.setter
    def sublayer(self, value: str) -> None:
        """Set layer 7 sublayer label."""
        self.layer_info.sublayer = value

    @property
    def timestamp(self) -> int:
        """Timestamp for ordering simultaneous effects."""
        return self.layer_info.timestamp

    @timestamp.setter
    def timestamp(self, value: int) -> None:
        """Set modifier timestamp."""
        self.layer_info.timestamp = value

    @property
    def duration(self) -> str:
        """How long this modifier lasts."""
        return self.layer_info.duration

    @duration.setter
    def duration(self, value: str) -> None:
        """Set modifier duration."""
        self.layer_info.duration = value

    @property
    def set_power(self) -> int | None:
        """Layer 7b set power, if any."""
        return self.pt.set_power

    @set_power.setter
    def set_power(self, value: int | None) -> None:
        """Set layer 7b power."""
        self.pt.set_power = value

    @property
    def set_toughness(self) -> int | None:
        """Layer 7b set toughness, if any."""
        return self.pt.set_toughness

    @set_toughness.setter
    def set_toughness(self, value: int | None) -> None:
        """Set layer 7b toughness."""
        self.pt.set_toughness = value

    @property
    def power_delta(self) -> int:
        """Layer 7c power bonus."""
        return self.pt.power_delta

    @power_delta.setter
    def power_delta(self, value: int) -> None:
        """Set layer 7c power bonus."""
        self.pt.power_delta = value

    @property
    def toughness_delta(self) -> int:
        """Layer 7c toughness bonus."""
        return self.pt.toughness_delta

    @toughness_delta.setter
    def toughness_delta(self, value: int) -> None:
        """Set layer 7c toughness bonus."""
        self.pt.toughness_delta = value

    @property
    def switch_pt(self) -> bool:
        """True when this modifier switches power and toughness (layer 7e)."""
        return self.pt.switch_pt

    @switch_pt.setter
    def switch_pt(self, value: bool) -> None:
        """Set layer 7e power/toughness switch."""
        self.pt.switch_pt = value

    @property
    def controller_override(self) -> int | None:
        """Layer 2 control-changing override, if any."""
        return self.characteristics.controller_override

    @controller_override.setter
    def controller_override(self, value: int | None) -> None:
        """Set layer 2 controller override."""
        self.characteristics.controller_override = value

    @property
    def added_types(self) -> tuple[str, ...]:
        """Layer 4 types granted by this modifier."""
        return self.characteristics.added_types

    @added_types.setter
    def added_types(self, value: tuple[str, ...]) -> None:
        """Set layer 4 added types."""
        self.characteristics.added_types = value

    @property
    def removed_types(self) -> tuple[str, ...]:
        """Layer 4 types removed by this modifier."""
        return self.characteristics.removed_types

    @removed_types.setter
    def removed_types(self, value: tuple[str, ...]) -> None:
        """Set layer 4 removed types."""
        self.characteristics.removed_types = value

    @property
    def set_colors(self) -> tuple[str, ...] | None:
        """Layer 5 color set, if this modifier defines colors."""
        return self.characteristics.set_colors

    @set_colors.setter
    def set_colors(self, value: tuple[str, ...] | None) -> None:
        """Set layer 5 colors."""
        self.characteristics.set_colors = value

    @property
    def granted_keywords(self) -> tuple[str, ...]:
        """Layer 6 keywords granted by this modifier."""
        return self.characteristics.granted_keywords

    @granted_keywords.setter
    def granted_keywords(self, value: tuple[str, ...]) -> None:
        """Set layer 6 granted keywords."""
        self.characteristics.granted_keywords = value
