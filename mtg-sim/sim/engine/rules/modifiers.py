"""Helpers for attaching and expiring continuous-effect modifiers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.core.game_object import Modifier, Permanent

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
        layer=7,
        sublayer='c',
        power_delta=power_delta,
        toughness_delta=toughness_delta,
        duration=DURATION_UNTIL_EOT,
    )
    perm.modifiers.append(modifier)
    return modifier


def clear_until_end_of_turn_modifiers(game: GameState) -> None:
    """Remove until-end-of-turn modifiers from all battlefield permanents."""
    for perm in game.zones.battlefield:
        perm.modifiers = [
            mod for mod in perm.modifiers if mod.duration != DURATION_UNTIL_EOT
        ]
