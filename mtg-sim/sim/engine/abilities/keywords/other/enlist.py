"""Enlist: tap a non-attacking creature when this attacks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.abilities.keywords._core import has_keyword
from engine.core.game_object import Permanent

if TYPE_CHECKING:
    from engine.core.game_state import GameState


def has_enlist(perm: Permanent) -> bool:
    """Return True when the permanent has enlist."""
    return has_keyword(perm, 'Enlist')


def apply_enlist_on_attack(
    game: GameState,
    attacker: Permanent,
    attacker_ids: list[str],
) -> str | None:
    """Tap an untapped non-attacking creature you control (simplified enlist)."""
    if not has_enlist(attacker):
        return None
    helper: Permanent | None = None
    for perm in game.zones.battlefield:
        if perm.controller_idx != attacker.controller_idx:
            continue
        if str(perm.obj_id) in attacker_ids:
            continue
        if 'Creature' not in perm.type_line or perm.tapped:
            continue
        helper = perm
        break
    if helper is None:
        return None
    helper.tapped = True
    if 'draw a card' in attacker.oracle_text.lower():
        return f"enlist {helper.name} for {attacker.name} (draw)"
    return f"enlisted {helper.name} for {attacker.name}"
