"""Morph and megamorph: cast face-down 2/2; turn face up for morph cost."""

from __future__ import annotations

import re

from deck_registry import CardInfo
from engine.abilities.keywords.actions.counters import put_plus_counters
from engine.abilities.keywords.other.face_down_turn import can_turn_up_face_down_keyword
from engine.abilities.keywords.registry import has_registered_keyword
from engine.core.game_object import Permanent
from engine.core.game_state import GameState
from engine.core.mana import ManaCost

_MORPH_COST_RE = re.compile(
    r'morph\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)
_MEGAMORPH_COST_RE = re.compile(
    r'megamorph\s*((?:\{[^}]+\})+)',
    re.IGNORECASE,
)

MORPH_FACE_DOWN_MANA = 3


def has_morph(card: CardInfo) -> bool:
    """Return True when the card has morph or megamorph."""
    oracle = card.oracle_text or ''
    return (
        has_registered_keyword(oracle, 'Morph')
        or has_registered_keyword(oracle, 'Megamorph')
        or bool(_MORPH_COST_RE.search(oracle))
        or bool(_MEGAMORPH_COST_RE.search(oracle))
    )


def has_megamorph(card: CardInfo) -> bool:
    """Return True when the card has megamorph."""
    oracle = card.oracle_text or ''
    return has_registered_keyword(oracle, 'Megamorph') or bool(
        _MEGAMORPH_COST_RE.search(oracle)
    )


def morph_turn_up_cost(card: CardInfo) -> ManaCost | None:
    """Parse the morph or megamorph cost to turn the card face up."""
    oracle = card.oracle_text or ''
    match = _MEGAMORPH_COST_RE.search(oracle) or _MORPH_COST_RE.search(oracle)
    if match is None:
        return None
    return ManaCost.parse(match.group(1))


def morph_turn_up_mana_needed(card: CardInfo) -> int:
    """Return generic mana to turn a morph creature face up."""
    cost = morph_turn_up_cost(card)
    if cost is None:
        return 0
    return cost.mana_value


def normalize_morph_cast(card: CardInfo, cast_for_morph: bool) -> bool:
    """Return whether this cast uses morph (face-down 2/2)."""
    return cast_for_morph and has_morph(card) and card.is_creature


def morph_face_down_mana_needed() -> tuple[int, int]:
    """Return mana and life to cast a creature face down with morph."""
    return MORPH_FACE_DOWN_MANA, 0


def can_turn_up_morph(
    perm: Permanent,
    game: GameState,
    controller_idx: int,
    phase: str,
) -> bool:
    """Return True when a face-down morph creature may be turned face up."""
    return can_turn_up_face_down_keyword(
        perm, game, controller_idx, phase, has_morph,
    )


def apply_turn_up_morph(perm: Permanent) -> str | None:
    """Turn a morph creature face up; megamorph adds a +1/+1 counter."""
    if not perm.face_down or perm.card_info is None:
        return None
    if not has_morph(perm.card_info):
        return None
    perm.face_down = False
    detail = f"turned {perm.name} face up"
    if has_megamorph(perm.card_info):
        put_plus_counters(perm, 1)
        detail = f"{detail} (megamorph +1/+1)"
    return detail
