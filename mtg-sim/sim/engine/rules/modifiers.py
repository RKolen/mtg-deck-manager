"""Helpers for attaching and expiring continuous-effect modifiers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.core.modifier import (
    Modifier,
    _ModifierCharacteristics,
    _ModifierLayer,
    _ModifierPt,
)
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState

DURATION_UNTIL_EOT = 'until_end_of_turn'


def add_until_eot_pt_modifier(
    perm: Permanent,
    power_delta: int = 0,
    toughness_delta: int = 0,
    *,
    source_obj_id: int = 0,
) -> Modifier:
    """Apply a layer-7c P/T bonus that expires at end of turn."""
    modifier = Modifier(
        source_obj_id=source_obj_id,
        layer_info=_ModifierLayer(layer=7, sublayer='c', duration=DURATION_UNTIL_EOT),
        pt=_ModifierPt(power_delta=power_delta, toughness_delta=toughness_delta),
    )
    perm.modifiers.append(modifier)
    return modifier


def add_until_eot_set_pt_modifier(
    perm: Permanent,
    power: int,
    toughness: int,
    *,
    source_obj_id: int = 0,
) -> Modifier:
    """Apply a layer-7b set P/T that expires at end of turn."""
    modifier = Modifier(
        source_obj_id=source_obj_id,
        layer_info=_ModifierLayer(layer=7, sublayer='b', duration=DURATION_UNTIL_EOT),
        pt=_ModifierPt(set_power=power, set_toughness=toughness),
    )
    perm.modifiers.append(modifier)
    return modifier


def add_switch_pt_modifier(
    perm: Permanent,
    *,
    duration: str = 'permanent',
    source_obj_id: int = 0,
) -> Modifier:
    """Apply a layer-7e power/toughness switch."""
    modifier = Modifier(
        source_obj_id=source_obj_id,
        layer_info=_ModifierLayer(layer=7, sublayer='e', duration=duration),
        pt=_ModifierPt(switch_pt=True),
    )
    perm.modifiers.append(modifier)
    return modifier


def add_control_modifier(
    perm: Permanent,
    controller_idx: int,
    *,
    duration: str = 'permanent',
    source_obj_id: int = 0,
) -> Modifier:
    """Apply a layer-2 control-changing effect."""
    modifier = Modifier(
        source_obj_id=source_obj_id,
        layer_info=_ModifierLayer(layer=2, duration=duration),
        characteristics=_ModifierCharacteristics(controller_override=controller_idx),
    )
    perm.modifiers.append(modifier)
    return modifier


def add_type_modifier(
    perm: Permanent,
    *,
    added_types: tuple[str, ...] = (),
    removed_types: tuple[str, ...] = (),
    duration: str = 'permanent',
    source_obj_id: int = 0,
) -> Modifier:
    """Apply a layer-4 type-changing effect."""
    modifier = Modifier(
        source_obj_id=source_obj_id,
        layer_info=_ModifierLayer(layer=4, duration=duration),
        characteristics=_ModifierCharacteristics(
            added_types=added_types,
            removed_types=removed_types,
        ),
    )
    perm.modifiers.append(modifier)
    return modifier


def add_color_modifier(
    perm: Permanent,
    colors: tuple[str, ...],
    *,
    duration: str = 'permanent',
    source_obj_id: int = 0,
) -> Modifier:
    """Apply a layer-5 color-changing effect."""
    modifier = Modifier(
        source_obj_id=source_obj_id,
        layer_info=_ModifierLayer(layer=5, duration=duration),
        characteristics=_ModifierCharacteristics(set_colors=colors),
    )
    perm.modifiers.append(modifier)
    return modifier


def add_keyword_grant_modifier(
    perm: Permanent,
    keywords: tuple[str, ...],
    *,
    duration: str = 'permanent',
    source_obj_id: int = 0,
) -> Modifier:
    """Apply a layer-6 ability-adding effect."""
    modifier = Modifier(
        source_obj_id=source_obj_id,
        layer_info=_ModifierLayer(layer=6, duration=duration),
        characteristics=_ModifierCharacteristics(granted_keywords=keywords),
    )
    perm.modifiers.append(modifier)
    return modifier


def clear_until_end_of_turn_modifiers(game: GameState) -> None:
    """Remove until-end-of-turn modifiers from all battlefield permanents."""
    for perm in game.zones.battlefield:
        perm.modifiers = [
            mod for mod in perm.modifiers if mod.duration != DURATION_UNTIL_EOT
        ]
